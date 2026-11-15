"""The outbox dispatcher (review focus 2): every event reaches every matching handler
at least once, and each handler's visible effect is committed exactly once, also when
a dispatcher dies in the middle of a batch or two dispatchers run at the same time.

Real commits and separate connections throughout (tests/real_db.py).
"""

import asyncio
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import Database
from app.core.metrics import render_metrics
from app.core.outbox import Event, EventActor, EventOutbox, emit
from app.core.principal import Principal
from app.modules.orgs.models import Organization
from app.worker.dispatcher import MAX_ATTEMPTS, Dispatcher
from app.worker.registry import HandlerRegistry
from app.worker.repository import OutboxRepository
from tests.conftest import json_lines
from tests.outbox_helpers import (
    Calls,
    delivered,
    due_now,
    effects,
    emit_committed,
    lane_row,
    outbox_row,
    registry_of,
    write_effect,
)
from tests.real_db import RealDb
from tests.support.plans import force_nested_loops

BACKEND = Path(__file__).resolve().parent.parent


async def test_each_handler_gets_each_event_once_when_all_succeed(real_db: RealDb) -> None:
    calls: Calls = Counter()
    ids = await emit_committed(real_db.database, real_db.org_id, 3)
    dispatcher = Dispatcher(real_db.database, registry_of(calls, ["a", "b"]))
    await dispatcher.drain()
    assert calls == Counter({(i, h): 1 for i in ids for h in ("a", "b")})
    for event_id in ids:
        assert await effects(real_db.database, event_id) == Counter({"a": 1, "b": 1})
        assert await delivered(real_db.database, event_id) == {"a", "b"}
        row = await outbox_row(real_db.database, event_id)
        assert row.dispatched_at is not None and row.routed_at is not None
        assert await lane_row(real_db.database, event_id, "a") is None  # nothing left
    await dispatcher.drain()  # nothing left: no handler runs again
    assert sum(calls.values()) == 6


async def test_handlers_only_get_the_types_they_asked_for(real_db: RealDb) -> None:
    seen: list[str] = []
    registry = HandlerRegistry()

    @registry.handler(("message", "channel.created"), "picky")
    async def _picky(session, event: Event) -> None:
        seen.append(event.type)

    assert [h.name for h in registry.for_type("message.created")] == ["picky"]
    assert [h.name for h in registry.for_type("channel.created")] == ["picky"]
    assert registry.for_type("channel.created_twice") == []
    assert registry.for_type("messages.created") == []
    with pytest.raises(ValueError, match="picky"):
        registry.handler("x", "picky")(_picky)


async def test_an_event_without_handlers_is_dispatched(real_db: RealDb) -> None:
    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    await Dispatcher(real_db.database, HandlerRegistry()).drain()
    assert (await outbox_row(real_db.database, event_id)).dispatched_at is not None


async def test_failed_handler_is_retried_and_others_are_not_repeated(real_db: RealDb) -> None:
    calls: Calls = Counter()
    failing = {"on": True}
    registry = registry_of(calls, ["a", "b"], b=lambda e: failing["on"])
    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    dispatcher = Dispatcher(real_db.database, registry)

    await dispatcher.drain()
    assert (await outbox_row(real_db.database, event_id)).dispatched_at is None
    lane = await lane_row(real_db.database, event_id, "b")
    assert lane is not None and lane.attempts == 1 and lane.failed_at is None
    wait = (lane.next_attempt_at - datetime.now(UTC)).total_seconds()
    assert 0 < wait <= 2.5  # 2^1 seconds
    assert await lane_row(real_db.database, event_id, "a") is None
    assert await delivered(real_db.database, event_id) == {"a"}
    assert await effects(real_db.database, event_id) == Counter({"a": 1})  # b rolled back

    await dispatcher.drain()  # not due yet: nothing runs
    assert calls[(event_id, "b")] == 1

    failing["on"] = False
    await due_now(real_db.database)
    await dispatcher.drain()
    assert calls == Counter({(event_id, "a"): 1, (event_id, "b"): 2})
    assert await effects(real_db.database, event_id) == Counter({"a": 1, "b": 1})
    row = await outbox_row(real_db.database, event_id)
    assert row.dispatched_at is not None and row.failed_at is None


async def test_the_wait_doubles_up_to_five_minutes(real_db: RealDb) -> None:
    calls: Calls = Counter()
    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    dispatcher = Dispatcher(real_db.database, registry_of(calls, ["a"], a=lambda e: True))
    waits = []
    for _ in range(MAX_ATTEMPTS - 1):
        await due_now(real_db.database)
        await dispatcher.dispatch_batch()
        lane = await lane_row(real_db.database, event_id, "a")
        assert lane is not None
        waits.append(round((lane.next_attempt_at - datetime.now(UTC)).total_seconds()))
    assert waits == [2, 4, 8, 16, 32, 64, 128, 256, 300]


async def test_event_fails_after_ten_attempts_and_is_reported(
    real_db: RealDb, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: Calls = Counter()
    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    dispatcher = Dispatcher(real_db.database, registry_of(calls, ["ok", "bad"], bad=lambda e: True))
    for _ in range(MAX_ATTEMPTS):
        await due_now(real_db.database)
        await dispatcher.dispatch_batch()
    row = await outbox_row(real_db.database, event_id)
    assert row.failed_at is not None and row.dispatched_at is None
    lane = await lane_row(real_db.database, event_id, "bad")
    assert lane is not None and lane.attempts == MAX_ATTEMPTS and lane.failed_at is not None
    assert calls == Counter({(event_id, "ok"): 1, (event_id, "bad"): MAX_ATTEMPTS})

    await due_now(real_db.database)
    await dispatcher.drain()  # a failed event is not tried again
    assert calls[(event_id, "bad")] == MAX_ATTEMPTS

    lines = [
        line for line in json_lines(capsys.readouterr().out) if line["message"] == "outbox.failed"
    ]
    assert len(lines) == 1 and lines[0]["level"] == "ERROR"
    assert lines[0]["event_id"] == str(event_id) and lines[0]["handlers"] == ["bad"]
    assert lines[0]["attempts"] == MAX_ATTEMPTS and lines[0]["type"] == "test.happened"
    metrics = render_metrics()[0].decode()
    assert 'herd_outbox_dispatch_total{handler="bad",result="failed"}' in metrics


async def test_log_never_contains_payload(
    real_db: RealDb, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "Vertraulicher-Nachrichtentext-4711"
    registry = HandlerRegistry()

    @registry.handler("test", "leaky")
    async def _leaky(session, event: Event) -> None:
        raise ValueError(f"cannot handle {event.payload['body']}")

    await emit_committed(real_db.database, real_db.org_id, payload={"body": secret})
    dispatcher = Dispatcher(real_db.database, registry)
    for _ in range(MAX_ATTEMPTS):
        await due_now(real_db.database)
        await dispatcher.dispatch_batch()
    out = capsys.readouterr().out
    messages = {line["message"] for line in json_lines(out)}
    assert {"outbox.handler_failed", "outbox.failed"} <= messages
    assert secret not in out


async def test_two_dispatchers_do_not_deliver_twice(real_db: RealDb) -> None:
    calls: Calls = Counter()
    ids = await emit_committed(real_db.database, real_db.org_id, 120)
    registry = HandlerRegistry()

    async def slow(session, event: Event) -> None:
        calls[(event.id, "slow")] += 1
        await asyncio.sleep(0.001)  # let the other dispatcher interleave
        await write_effect(session, event, "slow")

    registry.handler("test", "slow")(slow)
    url = get_settings().test_database_url
    first, second = Database(url), Database(url)  # separate pools, separate connections
    try:
        d1 = Dispatcher(first, registry, batch_size=10)
        d2 = Dispatcher(second, registry, batch_size=10)
        await asyncio.gather(d1.drain(), d2.drain())
    finally:
        await first.dispose()
        await second.dispose()
    assert calls == Counter({(i, "slow"): 1 for i in ids})
    for event_id in ids:
        assert await effects(real_db.database, event_id) == Counter({"slow": 1})
        assert (await outbox_row(real_db.database, event_id)).dispatched_at is not None


async def test_dispatched_events_are_removed_after_seven_days(real_db: RealDb) -> None:
    old, recent, pending = await emit_committed(real_db.database, real_db.org_id, 3)
    await Dispatcher(real_db.database, registry_of(Counter(), ["a"])).drain()
    now = datetime.now(UTC)
    async with real_db.database.session_factory() as session:
        for event_id, at in ((old, now - timedelta(days=8)), (recent, now - timedelta(days=6))):
            await session.execute(
                update(EventOutbox).where(EventOutbox.id == event_id).values(dispatched_at=at)
            )
        await session.execute(
            update(EventOutbox)
            .where(EventOutbox.id == pending)
            .values(dispatched_at=None, created_at=now - timedelta(days=30))
        )
        await session.commit()
    removed = await Dispatcher(real_db.database, HandlerRegistry(), cleanup_batch=1).cleanup()
    assert removed >= 1
    async with real_db.database.session_factory() as session:
        assert await session.get(EventOutbox, old) is None
        assert await session.get(EventOutbox, recent) is not None
        assert await session.get(EventOutbox, pending) is not None
    assert await delivered(real_db.database, old) == set()  # its records went with it


async def test_one_cleanup_batch_removes_at_most_its_limit_whatever_the_plan(
    session: AsyncSession, org: Organization
) -> None:
    """A batch over `IN (subquery … LIMIT n FOR UPDATE SKIP LOCKED)` removes more
    than n under a nested-loop plan; it must hold whatever plan is picked."""
    actor = EventActor(org.id, Principal.user(uuid.uuid4()))
    ids = []
    for _ in range(5):
        event = await emit(
            session,
            type="test.happened",
            actor=actor,
            space_id=None,
            subject_type="test",
            subject_id=uuid.uuid4(),
            payload={},
        )
        ids.append(event.id)
    long_ago = datetime(2001, 1, 1, tzinfo=UTC)
    await session.execute(
        update(EventOutbox).where(EventOutbox.id.in_(ids)).values(dispatched_at=long_ago)
    )
    await force_nested_loops(session)
    removed = await OutboxRepository(session).delete_dispatched_before(
        long_ago + timedelta(days=1), 2
    )
    left = select(func.count()).select_from(EventOutbox).where(EventOutbox.id.in_(ids))
    assert (removed, await session.scalar(left)) == (2, 3)


async def test_metrics_show_backlog_and_results(real_db: RealDb) -> None:
    calls: Calls = Counter()
    await emit_committed(real_db.database, real_db.org_id, 2)
    dispatcher = Dispatcher(real_db.database, registry_of(calls, ["metered"]))
    async with real_db.database.session_factory() as session:
        await session.execute(
            update(EventOutbox).values(created_at=datetime.now(UTC) - timedelta(seconds=90))
        )
        await session.commit()
    await dispatcher.update_metrics()
    text = render_metrics()[0].decode()
    assert "herd_outbox_pending 2.0" in text
    oldest = next(
        line for line in text.splitlines() if line.startswith("herd_outbox_oldest_pending_seconds ")
    )
    assert 89 <= float(oldest.split()[1]) < 120
    await dispatcher.drain()
    await dispatcher.update_metrics()
    text = render_metrics()[0].decode()
    assert "herd_outbox_pending 0.0" in text
    assert "herd_outbox_oldest_pending_seconds 0.0" in text
    assert 'herd_outbox_dispatch_total{handler="metered",result="ok"}' in text
