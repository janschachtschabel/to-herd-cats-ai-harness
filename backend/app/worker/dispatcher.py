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
- A handler hangs: every handler call has `handler_timeout` seconds
  (HERD_WORKER_HANDLER_TIMEOUT_SECONDS, default 30), enforced by an asyncio timeout
  and, for a lock or statement in the database, by the transaction's `lock_timeout`
  and `statement_timeout`. A timeout is a failed attempt like any other. A handler
  that timed out is not called again in the same batch (its other events stay due
  for the next pass, without an attempt counted), so one hang delays the batch's
  other handlers by at most the limit.
"""

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from enum import Enum

import app.models_registry  # noqa: F401 -- every model: handlers write to any table
from app.core.db import Database
from app.core.metrics import OUTBOX_DISPATCHES
from app.core.outbox import Event
from app.worker import registry as handler_registry
from app.worker.metrics import worker_metrics
from app.worker.registry import Handler, HandlerRegistry
from app.worker.repository import OutboxRepository

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
MAX_ATTEMPTS = 10
MAX_WAIT_SECONDS = 300
RETENTION = timedelta(days=7)
CLEANUP_BATCH = 1000
CLEANUP_EVERY_SECONDS = 60.0
HANDLER_TIMEOUT_SECONDS = 30.0  # default of HERD_WORKER_HANDLER_TIMEOUT_SECONDS


class Outcome(Enum):
    OK = "ok"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


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
        handler_timeout: float = HANDLER_TIMEOUT_SECONDS,
    ) -> None:
        self.database = database
        self.registry = registry if registry is not None else handler_registry.REGISTRY
        self.batch_size = batch_size
        self.handler_timeout = handler_timeout
        self.cleanup_batch = cleanup_batch
        self._last_cleanup: float | None = None

    async def dispatch_batch(self) -> int:
        """Claim and dispatch one batch; how many events it held."""
        async with self.database.session_factory() as session, session.begin():
            repo = OutboxRepository(session)
            rows = await repo.claim(self.batch_size)
            done = await repo.delivered([row.id for row in rows])
            dispatched = []
            stalled: set[str] = set()  # handlers that timed out in this batch
            for row in rows:
                event = Event.of(row)
                failed, skipped = [], False
                for handler in self.registry.for_type(event.type):
                    if (event.id, handler.name) in done:
                        continue
                    if handler.name in stalled:
                        skipped = True
                        continue
                    outcome = await self._try(event, handler)
                    if outcome is Outcome.TIMED_OUT:
                        stalled.add(handler.name)
                    if outcome is not Outcome.OK:
                        failed.append(handler.name)
                if not failed:
                    if not skipped:
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
        async with (
            asyncio.timeout(self.handler_timeout),
            self.database.session_factory() as session,
            session.begin(),
        ):
            repo = OutboxRepository(session)
            await repo.limit_time(max(1, int(self.handler_timeout * 1000)))
            if not await repo.record_delivery(event.id, handler.name):
                return False
            await handler.func(session, event)
        return True

    async def _try(self, event: Event, handler: Handler) -> Outcome:
        try:
            first = await self.deliver(event, handler)
        except TimeoutError:
            OUTBOX_DISPATCHES.labels(handler=handler.name, result="timeout").inc()
            _log_failure("outbox.handler_timeout", event, handler, "TimeoutError")
            return Outcome.TIMED_OUT
        except Exception as exc:
            if _is_timeout(exc):  # the database ended a lock wait or a statement
                OUTBOX_DISPATCHES.labels(handler=handler.name, result="timeout").inc()
                _log_failure("outbox.handler_timeout", event, handler, type(exc).__name__)
                return Outcome.TIMED_OUT
            OUTBOX_DISPATCHES.labels(handler=handler.name, result="error").inc()
            # Type only: a handler's error message may quote what it was handling.
            _log_failure("outbox.handler_failed", event, handler, type(exc).__name__)
            return Outcome.FAILED
        OUTBOX_DISPATCHES.labels(handler=handler.name, result="ok" if first else "duplicate").inc()
        return Outcome.OK

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


def _is_timeout(exc: BaseException) -> bool:
    """Postgres' lock_timeout or statement_timeout (SQLSTATE 55P03, 57014), however
    the driver and SQLAlchemy wrap it."""
    seen: BaseException | None = exc
    for _ in range(5):  # a few layers of wrapping at most
        if seen is None:
            break
        if getattr(seen, "sqlstate", None) in ("55P03", "57014"):
            return True
        seen = seen.__cause__ or getattr(seen, "orig", None)
    return False


def _log_failure(message: str, event: Event, handler: Handler, error: str) -> None:
    logger.warning(
        message,
        extra={
            "event_id": str(event.id),
            "type": event.type,
            "handler": handler.name,
            "error": error,
        },
    )


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
