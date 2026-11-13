"""Review focus 2, the hard cases: a dispatcher dies in the middle of a lane's batch
(in process, and a real process killed with SIGKILL), and another connection holds the
same delivery. Each handler's effect is committed exactly once; only missing
deliveries are made again. Real commits, separate connections.
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
from app.core.outbox import Event, EventDelivery, EventOutbox
from app.worker.dispatcher import Dispatcher
from tests.outbox_helpers import (
    Calls,
    delivered,
    effects,
    emit_committed,
    lane_row,
    outbox_row,
    registry_of,
    write_effect,
)
from tests.real_db import RealDb

BACKEND = Path(__file__).resolve().parent.parent


async def test_a_delivery_another_connection_holds_has_one_effect(real_db: RealDb) -> None:
    """Should another connection hold the same delivery (a worker of the previous
    release, which knows no lanes), the delivery record decides: the lane waits for it
    and then finds the handler delivered."""
    calls: Calls = Counter()
    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    url = get_settings().test_database_url
    other = Database(url)
    try:
        async with other.session_factory() as held:
            row = await held.get_one(EventOutbox, event_id)
            held.add(EventDelivery(event_id=event_id, handler="slow"))
            await write_effect(held, Event.of(row), "slow")
            await held.flush()  # written, not committed: the lane must wait
            dispatching = asyncio.create_task(
                Dispatcher(real_db.database, registry_of(calls, ["slow"])).drain()
            )
            await asyncio.sleep(0.3)
            assert not dispatching.done()
            await held.commit()
        await asyncio.wait_for(dispatching, timeout=10)
    finally:
        await other.dispose()
    assert calls[(event_id, "slow")] == 0
    assert await effects(real_db.database, event_id) == Counter({"slow": 1})
    assert (await outbox_row(real_db.database, event_id)).dispatched_at is not None


async def test_crash_in_one_lane_redelivers_only_missing(real_db: RealDb) -> None:
    """In process: lane `a` committed its batch, then lane `b`'s batch dies (the
    process is going down); its transaction, which holds b's effect, record and lane
    change, never commits."""

    class Crash(BaseException):
        pass

    calls: Calls = Counter()
    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    crashing = registry_of(calls, ["a"])

    @crashing.handler("test", "b")
    async def _dies(session, event: Event) -> None:
        await write_effect(session, event, "b")
        raise Crash()

    dispatcher = Dispatcher(real_db.database, crashing)
    assert (await dispatcher.route()).events == 1
    (a, b) = dispatcher.handlers
    assert await dispatcher.dispatch_lane(a) == 1
    with pytest.raises(Crash):
        await dispatcher.dispatch_lane(b)
    row = await outbox_row(real_db.database, event_id)
    assert row.dispatched_at is None
    lane = await lane_row(real_db.database, event_id, "b")
    assert lane is not None and lane.attempts == 0
    assert await lane_row(real_db.database, event_id, "a") is None
    assert await delivered(real_db.database, event_id) == {"a"}
    assert await effects(real_db.database, event_id) == Counter({"a": 1})

    await Dispatcher(real_db.database, registry_of(calls, ["a", "b"])).drain()
    assert calls == Counter({(event_id, "a"): 1, (event_id, "b"): 1})
    assert await effects(real_db.database, event_id) == Counter({"a": 1, "b": 1})
    assert (await outbox_row(real_db.database, event_id)).dispatched_at is not None


async def test_killed_worker_process_redelivers_only_missing(real_db: RealDb) -> None:
    """A real crash: a dispatcher in another process is killed (SIGKILL) while the
    second handler's lane transaction is open; the first handler's lane had committed. Postgres
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
