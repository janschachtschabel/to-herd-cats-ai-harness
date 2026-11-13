"""The outbox dispatcher (spec 4.3; without DBOS until M6, plan decision 1).

A batch is claimed in one transaction (`FOR NO KEY UPDATE SKIP LOCKED`, so parallel
dispatchers take disjoint batches). Each event goes to every matching handler that
has no delivery record yet, each in a transaction of its own that also writes the
record: the effect and the record are committed together or not at all. When every
handler has the event, the batch's transaction marks it dispatched.

- A handler fails: the others keep their deliveries; the event waits 2^attempts
  seconds (at most 5 minutes) and then goes only to the missing handlers. After
  MAX_ATTEMPTS failed passes it is marked failed and logged, without its payload.
- The dispatcher dies in the middle: the batch's transaction ends with the
  connection, its locks go, and the next pass hands the event to the missing
  handlers only.
- Two dispatchers ever holding the same event (a claim whose connection was lost
  while its handler ran on): the delivery record's primary key makes the second wait
  for the first and then skip.
"""

import logging
import time
from datetime import UTC, datetime, timedelta

import app.models_registry  # noqa: F401 -- every model: handlers write to any table
from app.core.db import Database
from app.core.metrics import OUTBOX_DISPATCHES, OUTBOX_OLDEST_PENDING, OUTBOX_PENDING
from app.core.outbox import Event
from app.worker import registry as handler_registry
from app.worker.registry import Handler, HandlerRegistry
from app.worker.repository import OutboxRepository

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
MAX_ATTEMPTS = 10
MAX_WAIT_SECONDS = 300
RETENTION = timedelta(days=7)
CLEANUP_BATCH = 1000
CLEANUP_EVERY_SECONDS = 60.0


def retry_wait(attempts: int) -> timedelta:
    """The wait after the `attempts`-th failed pass: 2, 4, 8 … seconds, at most 5 min."""
    return timedelta(seconds=min(2**attempts, MAX_WAIT_SECONDS))


class Dispatcher:
    def __init__(
        self,
        database: Database,
        registry: HandlerRegistry | None = None,
        *,
        batch_size: int = BATCH_SIZE,
        cleanup_batch: int = CLEANUP_BATCH,
    ) -> None:
        self.database = database
        self.registry = registry if registry is not None else handler_registry.REGISTRY
        self.batch_size = batch_size
        self.cleanup_batch = cleanup_batch
        self._last_cleanup: float | None = None

    async def dispatch_batch(self) -> int:
        """Claim and dispatch one batch; how many events it held."""
        async with self.database.session_factory() as session, session.begin():
            repo = OutboxRepository(session)
            rows = await repo.claim(self.batch_size)
            done = await repo.delivered([row.id for row in rows])
            dispatched = []
            for row in rows:
                event = Event.of(row)
                failed = [
                    handler.name
                    for handler in self.registry.for_type(event.type)
                    if (event.id, handler.name) not in done and not await self._try(event, handler)
                ]
                if not failed:
                    dispatched.append(event.id)
                elif (attempts := row.attempts + 1) >= MAX_ATTEMPTS:
                    await repo.mark_failed(event.id, attempts)
                    _report_failed(event, failed, attempts)
                else:
                    await repo.retry_later(event.id, attempts, retry_wait(attempts))
            await repo.mark_dispatched(dispatched)
        return len(rows)

    async def drain(self) -> None:
        """Dispatch until no event is due."""
        while await self.dispatch_batch():
            pass

    async def deliver(self, event: Event, handler: Handler) -> bool:
        """Run `handler` in its own transaction together with its delivery record;
        False (and the handler does not run) when the event was delivered to it already."""
        async with self.database.session_factory() as session, session.begin():
            if not await OutboxRepository(session).record_delivery(event.id, handler.name):
                return False
            await handler.func(session, event)
        return True

    async def _try(self, event: Event, handler: Handler) -> bool:
        try:
            first = await self.deliver(event, handler)
        except Exception as exc:
            OUTBOX_DISPATCHES.labels(handler=handler.name, result="error").inc()
            # Type only: a handler's error message may quote what it was handling.
            logger.warning(
                "outbox.handler_failed",
                extra={
                    "event_id": str(event.id),
                    "type": event.type,
                    "handler": handler.name,
                    "error": type(exc).__name__,
                },
            )
            return False
        OUTBOX_DISPATCHES.labels(handler=handler.name, result="ok" if first else "duplicate").inc()
        return True

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
        async with self.database.session_factory() as session:
            count, oldest = await OutboxRepository(session).backlog()
        OUTBOX_PENDING.set(count)
        age = (datetime.now(UTC) - oldest).total_seconds() if oldest is not None else 0.0
        OUTBOX_OLDEST_PENDING.set(max(age, 0.0))


def _report_failed(event: Event, handlers: list[str], attempts: int) -> None:
    for name in handlers:
        OUTBOX_DISPATCHES.labels(handler=name, result="failed").inc()
    logger.error(
        "outbox.failed",
        extra={
            "event_id": str(event.id),
            "type": event.type,
            "handlers": handlers,
            "attempts": attempts,
        },
    )
