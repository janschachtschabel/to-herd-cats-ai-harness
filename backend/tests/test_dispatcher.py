"""The outbox dispatcher (review focus 2): every event reaches every matching handler
at least once, and each handler's visible effect is committed exactly once, also when
a dispatcher dies in the middle of a batch or two dispatchers run at the same time.

Real commits and separate connections throughout (tests/real_db.py).
"""

import asyncio
import os
import signal
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import update

from app.core.config import get_settings
from app.core.db import Database
from app.core.metrics import render_metrics
from app.core.outbox import Event, EventOutbox
from app.worker.dispatcher import MAX_ATTEMPTS, Dispatcher
from app.worker.registry import HandlerRegistry
from tests.conftest import json_lines
from tests.outbox_helpers import (
    Calls,
    delivered,
    due_now,
    effects,
    emit_committed,
    outbox_row,
    registry_of,
    write_effect,
)
from tests.real_db import RealDb

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
        assert row.dispatched_at is not None and row.attempts == 0
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
    row = await outbox_row(real_db.database, event_id)
    assert row.dispatched_at is None and row.attempts == 1
    wait = (row.next_attempt_at - datetime.now(UTC)).total_seconds()
    assert 0 < wait <= 2.5  # 2^1 seconds
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
        row = await outbox_row(real_db.database, event_id)
        waits.append(round((row.next_attempt_at - datetime.now(UTC)).total_seconds()))
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
    assert row.attempts == MAX_ATTEMPTS
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


async def test_the_same_delivery_on_two_connections_has_one_effect(real_db: RealDb) -> None:
    """Should two dispatchers ever hold the same event (a claim whose connection was
    lost while its handler still ran), the delivery record decides: the second waits
    for the first and then finds the handler delivered."""
    calls: Calls = Counter()
    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    registry = HandlerRegistry()
    started = asyncio.Event()

    async def slow(session, event: Event) -> None:
        calls[(event.id, "slow")] += 1
        started.set()
        await asyncio.sleep(0.3)
        await write_effect(session, event, "slow")

    registry.handler("test", "slow")(slow)
    (handler,) = registry.for_type("test.happened")
    async with real_db.database.session_factory() as session:
        event = Event.of(await session.get_one(EventOutbox, event_id))
    url = get_settings().test_database_url
    first, second = Database(url), Database(url)
    try:
        d1, d2 = Dispatcher(first, registry), Dispatcher(second, registry)
        task = asyncio.create_task(d1.deliver(event, handler))
        await started.wait()
        results = [await d2.deliver(event, handler), await task]
    finally:
        await first.dispose()
        await second.dispose()
    assert sorted(results) == [False, True]
    assert calls[(event_id, "slow")] == 1
    assert await effects(real_db.database, event_id) == Counter({"slow": 1})


async def test_crash_between_handler_and_mark_redelivers_only_missing(real_db: RealDb) -> None:
    """In process: the dispatcher dies after its first handler committed; the batch's
    transaction (which would mark the event dispatched) never commits."""

    class Crash(BaseException):
        pass

    calls: Calls = Counter()
    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    crashing = registry_of(calls, ["a"])

    @crashing.handler("test", "b")
    async def _dies(session, event: Event) -> None:
        raise Crash()

    with pytest.raises(Crash):
        await Dispatcher(real_db.database, crashing).dispatch_batch()
    row = await outbox_row(real_db.database, event_id)
    assert row.dispatched_at is None and row.attempts == 0
    assert await delivered(real_db.database, event_id) == {"a"}

    await Dispatcher(real_db.database, registry_of(calls, ["a", "b"])).drain()
    assert calls == Counter({(event_id, "a"): 1, (event_id, "b"): 1})
    assert await effects(real_db.database, event_id) == Counter({"a": 1, "b": 1})
    assert (await outbox_row(real_db.database, event_id)).dispatched_at is not None


async def test_killed_worker_process_redelivers_only_missing(real_db: RealDb) -> None:
    """A real crash: a dispatcher in another process is killed (SIGKILL) while its
    second handler's transaction is open; its first handler had committed. Postgres
    drops the dead connections' locks and uncommitted work, and a new dispatcher
    delivers only what is missing."""
    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    env = {**os.environ, "HERD_TEST_DATABASE_URL": get_settings().test_database_url}
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "tests.outbox_crash_child",
        cwd=BACKEND,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        assert child.stdout is not None and child.stderr is not None
        line = await asyncio.wait_for(child.stdout.readline(), timeout=30)
        if line.strip() != b"in-second":
            pytest.fail((await child.stderr.read()).decode()[-3000:])
    finally:
        if child.returncode is None:
            child.send_signal(signal.SIGKILL)
        await child.wait()
    assert await delivered(real_db.database, event_id) == {"first"}

    calls: Calls = Counter()
    dispatcher = Dispatcher(real_db.database, registry_of(calls, ["first", "second"]))
    for _ in range(50):  # until Postgres has noticed the dead connection
        await dispatcher.drain()
        if (await outbox_row(real_db.database, event_id)).dispatched_at is not None:
            break
        await asyncio.sleep(0.1)
    assert calls == Counter({(event_id, "second"): 1})
    assert await effects(real_db.database, event_id) == Counter({"first": 1, "second": 1})


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
