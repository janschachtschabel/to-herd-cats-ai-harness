"""The outbox dispatcher (spec 4.3; without DBOS until M6, plan decision 1), one lane per
handler (review M4 P3, P10).

Routing: new events are taken in batches (`FOR NO KEY UPDATE SKIP LOCKED`) and get one
`event_lane` row per handler that wants them, in the transaction that marks them
routed; an event no handler wants is dispatched at once.

Lanes: every handler works off its own rows, independently of the others (the worker
runs each lane as a task of its own), so a backlog or a hang in one handler never
delays another. A lane's batch is one transaction (`lane.py`): it claims up to
`batch_size` rows (`FOR UPDATE SKIP LOCKED`), records the deliveries, runs the
handler on each event (a failing event does not fail its neighbours), drops the
delivered events' rows, counts a failure on the others and finishes the events whose
lanes are all done (`OutboxRepository.finish`). An effect, its delivery record and its
lane row are committed together or not at all.

- A handler fails: the lane waits 2^attempts seconds (at most 5 minutes) for that
  event. After MAX_ATTEMPTS failures the lane gives up: the row is kept with
  `failed_at`, the event is logged without its payload and marked failed once no
  other lane of it is left.
- The dispatcher dies in the middle: the batch's transaction ends with the
  connection, and the next batch takes the same rows again.
- Two workers take disjoint rows. Should two ever hold the same (event, handler) (a
  worker of the previous release, which knows no lanes), the delivery record's primary
  key makes the second wait for the first and then skip.
- A handler hangs: every call has `handler_timeout` seconds
  (HERD_WORKER_HANDLER_TIMEOUT_SECONDS, default 30), enforced by an asyncio timeout
  and, for a lock or statement in the database, by the transaction's `lock_timeout`
  and `statement_timeout`. A timeout is a failed attempt like any other, and the lane
  ends its batch there: its other events stay due for the next batch, without an
  attempt counted. No other lane waits for it.

Order: one worker hands a lane's events over in the order of their ids (the order
they were written in), as before; after a retry, or with several workers, there is
no order. Handlers of one event no longer run one after the other, and different
handlers may be at different events; no handler relies on either.
"""

import time
from asyncio import TaskGroup
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import app.models_registry  # noqa: F401 -- every model: handlers write to any table
from app.core.db import Database, run_after_commit
from app.worker import registry as handler_registry
from app.worker.lane import MAX_ATTEMPTS, Claimed, LaneBatch, count_failure, log_failure
from app.worker.metrics import worker_metrics
from app.worker.registry import Handler, HandlerRegistry
from app.worker.repository import OutboxRepository

BATCH_SIZE = 100  # a lane's events per transaction
ROUTE_BATCH = 500  # new events routed per transaction
RETENTION = timedelta(days=7)
CLEANUP_BATCH = 1000
CLEANUP_EVERY_SECONDS = 60.0
HANDLER_TIMEOUT_SECONDS = 30.0  # default of HERD_WORKER_HANDLER_TIMEOUT_SECONDS


@dataclass(frozen=True, slots=True)
class Routed:
    """What one routing batch did: how many events, and which handlers got rows."""

    events: int
    lanes: frozenset[str]


class Dispatcher:
    def __init__(
        self,
        database: Database,
        registry: HandlerRegistry | None = None,
        *,
        batch_size: int = BATCH_SIZE,
        route_batch: int = ROUTE_BATCH,
        cleanup_batch: int = CLEANUP_BATCH,
        handler_timeout: float = HANDLER_TIMEOUT_SECONDS,
    ) -> None:
        self.database = database
        self.registry = registry if registry is not None else handler_registry.REGISTRY
        self.batch_size = batch_size
        self.route_batch = route_batch
        self.handler_timeout = handler_timeout
        self.cleanup_batch = cleanup_batch
        self._last_cleanup: float | None = None

    @property
    def handlers(self) -> list[Handler]:
        return self.registry.handlers()

    async def route(self) -> Routed:
        """Route one batch of new events into their lanes."""
        async with self.database.session_factory() as session, session.begin():
            repo = OutboxRepository(session)
            rows = await repo.unrouted(self.route_batch)
            done = await repo.delivered([event_id for event_id, _ in rows])
            lanes, unwanted = [], []
            for event_id, event_type in rows:
                names = [
                    h.name
                    for h in self.registry.for_type(event_type)
                    if (event_id, h.name) not in done
                ]
                lanes += [(event_id, name) for name in names]
                if not names:
                    unwanted.append(event_id)
            await repo.add_lanes(lanes)
            await repo.mark_routed([event_id for event_id, _ in rows], unwanted)
        return Routed(len(rows), frozenset(name for _, name in lanes))

    async def dispatch_lane(self, handler: Handler) -> int:
        """One batch of the handler's lane; how many events it held."""
        broken: list[Claimed] = []  # the call during which the transaction broke
        try:
            async with self.database.session_factory() as session:
                async with session.begin():
                    batch = LaneBatch(session, handler, self.handler_timeout, broken)
                    count = await batch.run(self.batch_size)
                await run_after_commit(session)  # the handlers' (committed) actions
                return count
        except Exception as exc:
            if not broken:
                raise
            # The transaction itself broke during that call (a cancelled statement, a
            # lost connection): its batch is rolled back, that event's try is counted
            # alone so that it cannot hold the lane up for ever.
            event, attempts = broken[0]
            log_failure("outbox.handler_failed", event, handler, type(exc).__name__)
            async with self.database.session_factory() as session, session.begin():
                await count_failure(OutboxRepository(session), event, handler, attempts + 1)
            return 1

    async def dispatch_batch(self) -> int:
        """Route one batch, then one batch of every lane at once; how many events and
        lane rows that held (the worker runs these as loops of their own)."""
        routed = await self.route()
        async with TaskGroup() as group:
            tasks = [group.create_task(self.dispatch_lane(h)) for h in self.handlers]
        return routed.events + sum(task.result() for task in tasks)

    async def drain(self) -> None:
        """Dispatch until nothing is due."""
        while await self.dispatch_batch():
            pass

    async def cleanup(self) -> int:
        """Remove events dispatched more than RETENTION ago, batch by batch; how many."""
        cutoff = datetime.now(UTC) - RETENTION
        removed = 0
        while True:
            async with self.database.session_factory() as session, session.begin():
                count = await OutboxRepository(session).delete_dispatched_before(
                    cutoff, self.cleanup_batch
                )
            removed += count
            if count < self.cleanup_batch:
                return removed

    async def cleanup_if_due(self) -> None:
        now = time.monotonic()
        if self._last_cleanup is None or now - self._last_cleanup >= CLEANUP_EVERY_SECONDS:
            self._last_cleanup = now
            await self.cleanup()

    async def update_metrics(self) -> None:
        """The backlog gauges, read from the database."""
        async with self.database.session_factory() as session:
            repo = OutboxRepository(session)
            count, oldest = await repo.backlog()
            failed = await repo.failed_count()
        metrics = worker_metrics()
        metrics.pending.set(count)
        age = (datetime.now(UTC) - oldest).total_seconds() if oldest is not None else 0.0
        metrics.oldest_pending.set(max(age, 0.0))
        metrics.failed.set(failed)


__all__ = ["MAX_ATTEMPTS", "Dispatcher"]
