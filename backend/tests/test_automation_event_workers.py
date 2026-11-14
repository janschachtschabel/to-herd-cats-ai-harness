"""Event rules under real commits (plan M7 task 5, review focus 1 and 3): events
delivered by three dispatchers at once start one run; the rest wait, and the same
events handed over again change nothing; at the quiet time's end three due loops
fire the waiting events exactly once."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

import app.worker.handlers  # noqa: F401 -- registers every handler, ours too
from app.core.config import get_settings
from app.core.db import Database
from app.core.outbox import Event, EventOutbox
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.automations.event_models import AutomationEvent
from app.modules.automations.event_rules import on_event
from app.modules.automations.models import Automation, AutomationKind, AutomationState
from app.modules.spaces.repository import SpaceRepository
from app.worker.dispatcher import Dispatcher
from app.worker.due import DueLoop
from app.worker.registry import REGISTRY
from tests.factories import login
from tests.factories_automations import finish_runs, firings, runs_of
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.support.openai_stub import OpenAIStub
from tests.test_automation_due_loop import _place

WORKERS = 3
T0 = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
TICKETS = 6


@pytest.fixture
async def databases(real_db: RealDb) -> AsyncIterator[list[Database]]:
    made = [Database(get_settings().test_database_url) for _ in range(WORKERS)]
    yield made
    for database in made:
        await database.dispose()


async def _rule(real_db: RealDb, make_real_client: MakeRealClient, stub: OpenAIStub) -> Any:
    """A team space with a channel, the agent a member, a rule on new tickets there."""
    place = await _place(real_db, make_real_client, stub)
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space = (await owner.post("/api/spaces", json={"name": "Team", "kind": "team"})).json()
    channel = await owner.post(f"/api/spaces/{space['id']}/channels", json={"name": "neu"})
    assert channel.status_code == 201, channel.text
    async with real_db.database.session_factory() as session:
        await SpaceRepository(session).set_member(
            uuid.UUID(space["id"]), Principal.agent(place["agent"]), SpaceRole.EDITOR
        )
        rule = Automation(
            org_id=place["org"],
            owner_user_id=place["owner"],
            agent_id=place["agent"],
            conversation_id=uuid.UUID(channel.json()["id"]),
            instruction="Sieh dir neue Tickets an.",
            kind=AutomationKind.EVENT,
            event_type="ticket.created",
            quiet_seconds=300,
            state=AutomationState.ACTIVE,
        )
        session.add(rule)
        await session.commit()
    for n in range(TICKETS):
        r = await owner.post(f"/api/spaces/{space['id']}/tickets", json={"title": f"T{n}"})
        assert r.status_code == 201, r.text
    return rule.id


async def _handed(real_db: RealDb) -> list[Event]:
    async with real_db.database.session_factory() as session:
        rows = await session.scalars(
            select(EventOutbox).where(EventOutbox.type == "ticket.created")
        )
        return [Event.of(row) for row in rows]


async def _take(databases: list[Database], events: list[Event], now: datetime) -> None:
    """Every event handed to the rules at once, spread over the workers."""

    async def one(database: Database, event: Event) -> None:
        async with database.session_factory() as session, session.begin():
            await on_event(session, event, now)

    await asyncio.gather(*(one(databases[i % WORKERS], e) for i, e in enumerate(events)))


async def test_the_worker_hands_events_to_the_rules(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    rule_id = await _rule(real_db, make_real_client, openai_stub)
    await Dispatcher(real_db.database, REGISTRY).drain()
    async with real_db.database.session_factory() as session:
        assert len(await runs_of(session, rule_id)) == 1
        assert len(list(await session.scalars(select(AutomationEvent)))) == TICKETS


async def test_three_workers_start_one_run_and_fire_the_rest_once(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    databases: list[Database],
) -> None:
    rule_id = await _rule(real_db, make_real_client, openai_stub)
    handed = await _handed(real_db)
    await _take(databases, handed, T0)
    end = T0 + timedelta(seconds=300)
    async with real_db.database.session_factory() as session:
        assert len(await runs_of(session, rule_id)) == 1
        [first] = await firings(session, rule_id)
        rule = await session.get(Automation, rule_id)
        assert rule is not None and (rule.quiet_until, rule.next_due_at) == (end, end)
        taken = list(await session.scalars(select(AutomationEvent)))
        assert len(taken) == TICKETS
        assert sum(1 for e in taken if e.firing_id == first.id) == 1
        await finish_runs(session)
        await session.commit()
    await _take(databases, handed, end - timedelta(seconds=1))  # handed over again
    clock = SettableClock(end)
    loops = [DueLoop(database, clock=clock) for database in databases]
    assert sum(await asyncio.gather(*(loop.pass_once() for loop in loops))) == 1
    assert sum(await asyncio.gather(*(loop.pass_once() for loop in loops))) == 0
    async with real_db.database.session_factory() as session:
        logged = await firings(session, rule_id)
        assert [f.outcome for f in logged] == ["started", "started"]
        runs = await runs_of(session, rule_id)
        assert sorted(r.id for r in runs) == sorted(f.run_id for f in logged)  # type: ignore[type-var]
        taken = list(await session.scalars(select(AutomationEvent)))
        assert len(taken) == TICKETS
        assert sum(1 for e in taken if e.firing_id == logged[1].id) == TICKETS - 1
        rule = await session.get(Automation, rule_id)
        assert rule is not None and rule.next_due_at is None
