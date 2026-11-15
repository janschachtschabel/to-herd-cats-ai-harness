"""Retention of the automations' log (plan M7 task 11): the worker removes terms
older than FIRING_RETENTION (with the events they took) and events a term took more
than EVENT_RETENTION ago, in bounded batches, but never what a run still open may
read (its term, the events its term took) and never an event that still waits for
an active rule's quiet time to end, however old. Waiting events of a deleted rule go,
and those a paused rule took in more than EVENT_RETENTION ago (review M7, finding
11). Real commits (the due loop's own sessions)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.run_models import Run, RunState
from app.modules.automations.event_models import AutomationEvent
from app.modules.automations.models import (
    Automation,
    AutomationFiring,
    AutomationKind,
    AutomationState,
    FiringOutcome,
    PausedReason,
)
from app.worker.due import EVENT_RETENTION, FIRING_RETENTION, DueLoop
from tests.factories_automations import finish_runs
from tests.real_db import MakeRealClient, RealDb
from tests.support.clock import SettableClock
from tests.support.openai_stub import OpenAIStub
from tests.test_automation_due_loop import _place

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


async def _rule(real_db: RealDb, place: dict) -> uuid.UUID:
    """An event rule (a DM place is enough for the log's rows)."""
    async with real_db.database.session_factory() as session:
        rule = Automation(
            org_id=place["org"],
            owner_user_id=place["owner"],
            agent_id=place["agent"],
            conversation_id=place["dm"],
            instruction="Sieh nach.",
            kind=AutomationKind.EVENT,
            event_type="ticket.created",
            quiet_seconds=300,
            state=AutomationState.ACTIVE,
        )
        session.add(rule)
        await session.commit()
        return rule.id


def _firing(place: dict, rule_id: uuid.UUID, at: datetime, outcome: FiringOutcome) -> Any:
    return AutomationFiring(
        org_id=place["org"],
        automation_id=rule_id,
        due_at=at,
        fired_at=at,
        outcome=outcome,
        instruction="Sieh nach." if outcome == FiringOutcome.STARTED else None,
    )


def _event(
    place: dict, rule_id: uuid.UUID, firing_id: uuid.UUID | None, taken_at: datetime = NOW
) -> AutomationEvent:
    return AutomationEvent(
        org_id=place["org"],
        automation_id=rule_id,
        event_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),
        ids={},
        depth=0,
        firing_id=firing_id,
        taken_at=taken_at,
    )


async def _started_run(session: AsyncSession, place: dict, rule_id: uuid.UUID) -> uuid.UUID:
    """An open run of the rule (queued), as a term starts one."""
    run = Run(
        org_id=place["org"],
        agent_id=place["agent"],
        user_id=place["owner"],
        conversation_id=place["dm"],
        automation_id=rule_id,
        lane_id=rule_id,
        state=RunState.QUEUED,
    )
    session.add(run)
    await session.flush()
    return run.id


async def _log(real_db: RealDb) -> tuple[set[datetime], int, int]:
    """The terms left (their times), the events left, those of them waiting."""
    async with real_db.database.session_factory() as session:
        terms = set((await session.scalars(select(AutomationFiring.fired_at))).all())
        events = int(await session.scalar(select(func.count()).select_from(AutomationEvent)) or 0)
        waiting = await session.scalar(
            select(func.count()).where(AutomationEvent.firing_id.is_(None))
        )
        return terms, events, int(waiting or 0)


async def test_old_terms_and_taken_events_go_and_waiting_events_stay(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    place = await _place(real_db, make_real_client, openai_stub)
    rule_id = await _rule(real_db, place)
    ancient = NOW - FIRING_RETENTION - timedelta(days=1)
    old = NOW - EVENT_RETENTION - timedelta(hours=1)
    recent = NOW - EVENT_RETENTION + timedelta(hours=1)
    async with real_db.database.session_factory() as session:
        terms = {
            at: _firing(place, rule_id, at, FiringOutcome.SKIPPED_DEPTH)
            for at in (ancient, old, recent)
        }
        session.add_all(terms.values())
        await session.flush()
        session.add_all([_event(place, rule_id, f.id) for f in terms.values()])
        # waiting for a quiet time's end since long before every cutoff: never removed
        session.add_all([_event(place, rule_id, None) for _ in range(2)])
        await session.commit()
    loop = DueLoop(real_db.database, clock=SettableClock(NOW))
    assert await loop.cleanup() == (1, 2)  # the ancient term (its event with it); old's event
    left, events, waiting = await _log(real_db)
    assert left == {old, recent}
    assert (events, waiting) == (3, 2)  # recent's event and the two waiting
    assert await loop.cleanup() == (0, 0)


async def test_what_an_open_run_may_still_read_stays(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    place = await _place(real_db, make_real_client, openai_stub)
    rule_id = await _rule(real_db, place)
    ancient = NOW - FIRING_RETENTION - timedelta(days=1)
    async with real_db.database.session_factory() as session:
        term = _firing(place, rule_id, ancient, FiringOutcome.STARTED)
        term.run_id = await _started_run(session, place, rule_id)
        session.add(term)
        await session.flush()
        session.add(_event(place, rule_id, term.id))
        await session.commit()
    loop = DueLoop(real_db.database, clock=SettableClock(NOW))
    assert await loop.cleanup() == (0, 0)  # its run is open: the term and its event stay
    async with real_db.database.session_factory() as session:
        await finish_runs(session)
        await session.commit()
        assert await session.scalar(select(Run.state)) == RunState.DONE
    assert await loop.cleanup() == (1, 1)  # now both go
    assert await _log(real_db) == (set(), 0, 0)


async def test_the_cleanup_goes_in_bounded_batches_at_most_once_a_while(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    place = await _place(real_db, make_real_client, openai_stub)
    rule_id = await _rule(real_db, place)
    ancient = NOW - FIRING_RETENTION - timedelta(days=1)
    async with real_db.database.session_factory() as session:
        session.add_all(
            [
                _firing(place, rule_id, ancient + timedelta(minutes=n), FiringOutcome.SKIPPED_BUSY)
                for n in range(5)
            ]
        )
        await session.commit()
    loop = DueLoop(real_db.database, clock=SettableClock(NOW), cleanup_batch=2)
    assert await loop.cleanup_if_due() == (5, 0)  # three transactions of at most two
    async with real_db.database.session_factory() as session:
        session.add(_firing(place, rule_id, ancient, FiringOutcome.SKIPPED_BUSY))
        await session.commit()
    assert await loop.cleanup_if_due() is None  # not again so soon
    assert len((await _log(real_db))[0]) == 1


async def test_waiting_events_of_a_deleted_rule_and_of_one_paused_long_go(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    place = await _place(real_db, make_real_client, openai_stub)
    rules = {name: await _rule(real_db, place) for name in ("gone", "long", "short", "busy")}
    long_ago, lately = NOW - EVENT_RETENTION - timedelta(days=1), NOW - timedelta(days=1)
    async with real_db.database.session_factory() as session:
        for name, state in (("gone", "deleted"), ("long", "paused"), ("short", "paused")):
            rule = await session.get(Automation, rules[name])
            assert rule is not None
            rule.state = AutomationState(state)
            rule.paused_reason = PausedReason.MANUAL if state == "paused" else None
        session.add_all(
            [
                _event(place, rules["gone"], None, lately),
                _event(place, rules["long"], None, long_ago),
                _event(place, rules["short"], None, lately),
                _event(place, rules["busy"], None, long_ago),  # active: it fires them
            ]
        )
        await session.commit()
    loop = DueLoop(real_db.database, clock=SettableClock(NOW))
    assert await loop.cleanup() == (0, 2)
    async with real_db.database.session_factory() as session:
        left = set(await session.scalars(select(AutomationEvent.automation_id)))
    assert left == {rules["short"], rules["busy"]}
