"""The due loop under real commits (plan M7 task 2, review focus 1): three loops on
one database, each with connections of its own, fire every term exactly once; a
crash between firing and commit loses no term and doubles none; a term another
worker holds is passed over; the worker serves the loop."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import Database
from app.core.metrics import REGISTRY
from app.modules.automations.firing import fire_next
from app.modules.users.models import User
from app.worker.due import DueLoop
from app.worker.main import Worker
from tests.factories import login
from tests.factories_agents import assign_default, make_connection
from tests.factories_automations import automation_row, finish_runs, firings, runs_of
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.support.openai_stub import OpenAIStub
from tests.test_access import actor_of

T0 = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
LOOPS = 3


async def _place(real_db: RealDb, make_real_client: MakeRealClient, stub: OpenAIStub) -> dict:
    """An active agent and the owner's DM with it, committed."""
    from app.modules.agents.schemas import AgentCreate
    from app.modules.agents.service import AgentService

    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    connection = await make_connection(owner, stub)
    await assign_default(owner, connection)
    async with real_db.database.session_factory() as session:
        boss = await session.scalar(select(User).where(User.email == real_db.owner_email))
        assert boss is not None
        body = {
            "name": "Ava",
            "connection_id": connection["id"],
            "model": "m1",
            "responsible_user_id": boss.id,
            "status": "active",
        }
        agent = await AgentService(session).create(
            await actor_of(session, boss), AgentCreate.model_validate(body)
        )
        await session.commit()
    dm = (await owner.post("/api/dms", json={"agent_id": str(agent.id)})).json()
    return {"org": boss.org_id, "owner": boss.id, "agent": agent.id, "dm": dm["id"]}


async def _automations(real_db: RealDb, place: dict, count: int) -> list[uuid.UUID]:
    async with real_db.database.session_factory() as session:
        rows = [
            automation_row(place["org"], place["owner"], place["agent"], place["dm"], due=T0)
            for _ in range(count)
        ]
        session.add_all(rows)
        await session.commit()
        return [row.id for row in rows]


@pytest.fixture
async def databases(real_db: RealDb) -> AsyncIterator[list[Database]]:
    """One `Database` (engine, pool) per loop, as separate workers have."""
    made = [Database(get_settings().test_database_url) for _ in range(LOOPS)]
    yield made
    for database in made:
        await database.dispose()


async def test_three_loops_fire_every_term_exactly_once(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    databases: list[Database],
) -> None:
    place = await _place(real_db, make_real_client, openai_stub)
    ids = await _automations(real_db, place, 12)
    clock = SettableClock(T0)
    loops = [DueLoop(database, clock=clock) for database in databases]
    rounds = 4
    for _ in range(rounds):
        fired = await asyncio.gather(*(loop.pass_once() for loop in loops))
        assert sum(fired) == len(ids)
        async with real_db.database.session_factory() as session:
            await finish_runs(session)  # the runs answered before the next term
            await session.commit()
        clock.advance(timedelta(hours=1))
    async with real_db.database.session_factory() as session:
        for automation_id in ids:
            logged = await firings(session, automation_id)
            assert [f.due_at for f in logged] == [T0 + timedelta(hours=h) for h in range(rounds)]
            assert {f.outcome for f in logged} == {"started"}
            runs = await runs_of(session, automation_id)
            assert sorted(r.id for r in runs) == sorted(f.run_id for f in logged)  # type: ignore[type-var]


async def test_a_crash_before_the_commit_loses_no_term_and_doubles_none(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    databases: list[Database],
) -> None:
    place = await _place(real_db, make_real_client, openai_stub)
    [automation_id] = await _automations(real_db, place, 1)
    crashing, surviving = databases[0], databases[1]
    async with crashing.session_factory() as session:
        await session.begin()
        fired = await fire_next(session, T0)
        assert fired is not None and fired.automation_id == automation_id
        await session.rollback()  # the worker dies before its commit
    clock = SettableClock(T0 + timedelta(seconds=20))
    loop = DueLoop(surviving, clock=clock)
    assert await loop.pass_once() == 1
    assert await loop.pass_once() == 0
    async with real_db.database.session_factory() as session:
        [logged] = await firings(session, automation_id)
        assert (logged.due_at, logged.outcome) == (T0, "started")
        assert [r.id for r in await runs_of(session, automation_id)] == [logged.run_id]


async def test_a_term_another_worker_is_firing_is_passed_over(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
    databases: list[Database],
) -> None:
    place = await _place(real_db, make_real_client, openai_stub)
    [automation_id] = await _automations(real_db, place, 1)
    holding, other = databases[0], databases[1]
    loop = DueLoop(other, clock=SettableClock(T0))
    async with holding.session_factory() as session, session.begin():
        assert await fire_next(session, T0) is not None  # holds the row, not committed
        passed = await asyncio.wait_for(loop.pass_once(), timeout=5)  # no waiting on it
        assert passed == 0
    assert await loop.pass_once() == 0  # committed: its next term is not due yet
    async with real_db.database.session_factory() as session:
        assert len(await firings(session, automation_id)) == 1


def _counted(outcome: str) -> float:
    labels = {"outcome": outcome}
    return REGISTRY.get_sample_value("herd_automation_firings_total", labels) or 0.0


async def test_the_worker_serves_the_due_loop(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    from app.worker.dispatcher import Dispatcher
    from app.worker.registry import HandlerRegistry

    place = await _place(real_db, make_real_client, openai_stub)
    [automation_id] = await _automations(real_db, place, 1)
    before = _counted("started")
    due = DueLoop(real_db.database, clock=SettableClock(T0))
    worker = Worker(Dispatcher(real_db.database, HandlerRegistry()), due=due)
    task = asyncio.create_task(worker.serve())

    async def logged() -> int:
        async with real_db.database.session_factory() as session:
            return len(await firings(session, automation_id))

    try:
        for _ in range(200):
            if await logged():
                break
            await asyncio.sleep(0.05)
    finally:
        worker.should_exit = True
        await asyncio.wait_for(task, timeout=10)
    assert await logged() == 1
    assert _counted("started") == before + 1
