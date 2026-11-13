"""Review focus 2, the hard cases: a dispatcher dies in the middle of a batch (in
process, and a real process killed with SIGKILL), and two dispatchers hold the same
event. Each handler's effect is committed exactly once; only missing deliveries are
made again. Real commits, separate connections.
"""

import asyncio
import os
import signal
import sys
from collections import Counter
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.db import Database
from app.core.outbox import Event, EventOutbox
from app.worker.dispatcher import Dispatcher
from app.worker.registry import HandlerRegistry
from tests.outbox_helpers import (
    Calls,
    delivered,
    effects,
    emit_committed,
    outbox_row,
    registry_of,
    write_effect,
)
from tests.real_db import RealDb

BACKEND = Path(__file__).resolve().parent.parent


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
