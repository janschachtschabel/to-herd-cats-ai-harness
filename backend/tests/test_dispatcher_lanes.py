"""The dispatcher's lanes (review M4 P3, P10): each handler works off its own lane in
batches, one transaction per batch with a savepoint per event, so one handler's
backlog or hang never delays another, a failing event does not fail its neighbours,
and a burst costs a few transactions instead of one per (event, handler). Real
commits and separate connections throughout (tests/real_db.py)."""

import asyncio
import time
from collections import Counter

from sqlalchemy import event as sa_event
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import Database
from app.core.outbox import Event
from app.worker.dispatcher import Dispatcher
from app.worker.main import Worker
from app.worker.registry import HandlerRegistry
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


async def test_a_hanging_handler_does_not_delay_the_others(real_db: RealDb) -> None:
    """P10: while one handler hangs on every event, the others deliver at once."""
    registry = HandlerRegistry()
    seen: dict[str, float] = {}

    @registry.handler("test", "hangs")
    async def _hangs(session, event: Event) -> None:
        await asyncio.sleep(3600)

    @registry.handler("test", "prompt")
    async def _prompt(session, event: Event) -> None:
        seen[str(event.id)] = time.monotonic()

    worker = Worker(Dispatcher(real_db.database, registry, handler_timeout=15))
    task = asyncio.create_task(worker.serve())
    try:
        async with asyncio.timeout(5):
            while not worker.ready:  # noqa: ASYNC110 -- the loops are up
                await asyncio.sleep(0.02)
        started = time.monotonic()
        ids = await emit_committed(real_db.database, real_db.org_id, 4)
        async with asyncio.timeout(8):  # far below one time limit of `hangs`
            while len(seen) < 4:  # noqa: ASYNC110 -- the worker's lanes
                await asyncio.sleep(0.02)
        assert max(seen.values()) - started < 8
        for event_id in ids:
            assert await delivered(real_db.database, event_id) == {"prompt"}
    finally:
        worker.should_exit = True
        await asyncio.wait_for(task, timeout=30)


async def test_a_failing_event_does_not_fail_its_neighbours(real_db: RealDb) -> None:
    calls: Calls = Counter()
    ids = await emit_committed(real_db.database, real_db.org_id, 5)
    poisoned = ids[2]
    registry = registry_of(calls, ["picky"], picky=lambda e: e.id == poisoned)
    dispatcher = Dispatcher(real_db.database, registry)
    await dispatcher.drain()
    for event_id in ids:
        if event_id == poisoned:
            assert await effects(real_db.database, event_id) == Counter()  # rolled back
            assert await delivered(real_db.database, event_id) == set()
            lane = await lane_row(real_db.database, event_id, "picky")
            assert lane is not None and lane.attempts == 1
        else:
            assert await effects(real_db.database, event_id) == Counter({"picky": 1})
            assert (await outbox_row(real_db.database, event_id)).dispatched_at is not None


async def test_a_batch_costs_one_transaction_per_lane(real_db: RealDb) -> None:
    """60 events for two handlers: routing and each lane's batch commit once each
    (the dispatcher of M4 committed 60 x 2 handler transactions and a batch)."""
    calls: Calls = Counter()
    ids = await emit_committed(real_db.database, real_db.org_id, 60)
    commits: list[int] = []
    engine = real_db.database.engine.sync_engine

    def _count(_connection: object) -> None:
        commits.append(1)

    sa_event.listen(engine, "commit", _count)
    try:
        dispatcher = Dispatcher(real_db.database, registry_of(calls, ["a", "b"]))
        assert await dispatcher.dispatch_batch() == 60 * 3
    finally:
        sa_event.remove(engine, "commit", _count)
    assert len(commits) == 3
    assert calls == Counter({(i, h): 1 for i in ids for h in ("a", "b")})
    for event_id in ids:
        assert (await outbox_row(real_db.database, event_id)).dispatched_at is not None


async def test_a_timed_out_batch_leaves_the_rest_due_and_undelivered(real_db: RealDb) -> None:
    """The events after a timeout in a batch were recorded as delivered with the batch;
    those records are taken back, so they are delivered later and not lost."""
    registry = HandlerRegistry()
    hanging = {"on": True}
    calls: Counter[str] = Counter()

    @registry.handler("test", "sometimes")
    async def _sometimes(session, event: Event) -> None:
        calls[str(event.id)] += 1
        if hanging["on"]:
            await asyncio.sleep(3600)
        await write_effect(session, event, "sometimes")

    ids = await emit_committed(real_db.database, real_db.org_id, 3)
    dispatcher = Dispatcher(real_db.database, registry, handler_timeout=0.3)
    await dispatcher.dispatch_batch()
    assert [await delivered(real_db.database, i) for i in ids] == [set(), set(), set()]
    hanging["on"] = False
    await due_now(real_db.database)
    await dispatcher.drain()
    for event_id in ids:
        assert await effects(real_db.database, event_id) == Counter({"sometimes": 1})
        assert (await outbox_row(real_db.database, event_id)).dispatched_at is not None


async def test_a_handler_that_breaks_the_transaction_costs_one_attempt(real_db: RealDb) -> None:
    """A handler whose call leaves the batch's transaction unusable (here: its
    connection is ended) rolls the batch back; that event's try is counted on its own,
    so it cannot hold its lane up for ever, and its neighbours go through next time."""
    calls: Calls = Counter()
    registry = registry_of(calls, ["fine"])
    ids = await emit_committed(real_db.database, real_db.org_id, 3)
    poisoned = ids[1]

    @registry.handler("test", "breaks")
    async def _breaks(session, event: Event) -> None:
        if event.id == poisoned:
            await session.execute(text("SELECT pg_terminate_backend(pg_backend_pid())"))
        await write_effect(session, event, "breaks")

    dispatcher = Dispatcher(real_db.database, registry)
    await dispatcher.drain()
    lane = await lane_row(real_db.database, poisoned, "breaks")
    assert lane is not None and lane.attempts == 1
    for event_id in ids:
        expected = {"fine": 1} if event_id == poisoned else {"fine": 1, "breaks": 1}
        assert await effects(real_db.database, event_id) == Counter(expected)


async def test_an_event_fails_only_when_its_last_lane_is_done(real_db: RealDb) -> None:
    calls: Calls = Counter()
    (event_id,) = await emit_committed(real_db.database, real_db.org_id)
    registry = registry_of(calls, ["bad", "late"], bad=lambda e: True)
    dispatcher = Dispatcher(real_db.database, registry)
    await dispatcher.route()
    bad, late = dispatcher.handlers
    for _ in range(10):  # MAX_ATTEMPTS
        await due_now(real_db.database)
        await dispatcher.dispatch_lane(bad)
    row = await outbox_row(real_db.database, event_id)
    assert row.failed_at is None and row.dispatched_at is None  # `late` still waits
    await dispatcher.dispatch_lane(late)
    row = await outbox_row(real_db.database, event_id)
    assert row.failed_at is not None and row.dispatched_at is None
    assert await effects(real_db.database, event_id) == Counter({"late": 1})


async def test_two_workers_with_failing_neighbours_have_each_effect_once(
    real_db: RealDb,
) -> None:
    """Two workers (separate pools) run their lanes at once over 150 events; one handler
    fails every seventh event once. Every effect is committed exactly once."""
    calls: Calls = Counter()
    failed_once: set[object] = set()

    def flaky(event: Event) -> bool:
        if event.payload["i"] % 7 == 0 and event.id not in failed_once:
            failed_once.add(event.id)
            return True
        return False

    registry = registry_of(calls, ["steady", "flaky"], flaky=flaky)
    ids = await emit_committed(real_db.database, real_db.org_id, 150)
    url = get_settings().test_database_url
    first, second = Database(url), Database(url)
    try:
        d1 = Dispatcher(first, registry, batch_size=10, route_batch=40)
        d2 = Dispatcher(second, registry, batch_size=10, route_batch=40)
        await asyncio.gather(d1.drain(), d2.drain())
        await due_now(real_db.database)
        await asyncio.gather(d1.drain(), d2.drain())
    finally:
        await first.dispose()
        await second.dispose()
    assert calls[(ids[0], "flaky")] == 2 and calls[(ids[0], "steady")] == 1
    for event_id in ids:
        assert await effects(real_db.database, event_id) == Counter({"steady": 1, "flaky": 1})
        assert (await outbox_row(real_db.database, event_id)).dispatched_at is not None
