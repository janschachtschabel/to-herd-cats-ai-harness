"""One batch of a handler's lane (`Dispatcher.dispatch_lane`), in the batch's transaction.

The batch claims its rows, records the deliveries and then runs the handler on its
events one after the other inside one savepoint: in the common case nobody fails,
and the batch costs two statements beyond its handler's own (review M4 P3). Should
an event fail, that savepoint is rolled back, the failure is counted, and the batch
runs again from its start with a savepoint per event, so the failing event's
neighbours keep their effects (the failed one is not run again). A timeout ends the
batch at its event: the events after it stay due, without an attempt counted.

A handler's after-commit actions (`core.db.after_commit`, e.g. counting a metric) run
once the batch has committed (`Dispatcher.dispatch_lane`); those of a call whose
savepoint was rolled back are dropped with it.

Every handler call has `timeout` seconds (asyncio, with a small grace so that the
transaction's own `lock_timeout`/`statement_timeout` end a database wait first). A
failure takes its delivery record back and makes the lane wait 2^attempts seconds
(at most 5 minutes) for the event; after MAX_ATTEMPTS the lane gives up on it.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import db_errors
from app.core.db import after_commit_mark, discard_after_commit_since
from app.core.metrics import OUTBOX_DISPATCHES
from app.core.outbox import Event, one_notify
from app.worker.registry import Handler
from app.worker.repository import OutboxRepository

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 10
MAX_WAIT_SECONDS = 300
GRACE_SECONDS = 0.25  # the database's own limits end a database wait first

Claimed = tuple[Event, int]  # an event and its lane's failed tries so far


class Outcome(Enum):
    OK = "ok"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class _Failure(Exception):
    def __init__(self, index: int, outcome: Outcome) -> None:
        self.index, self.outcome = index, outcome


def retry_wait(attempts: int) -> timedelta:
    """The wait after the `attempts`-th failed try: 2, 4, 8 … seconds, at most 5 min."""
    return timedelta(seconds=min(2**attempts, MAX_WAIT_SECONDS))


@dataclass
class LaneBatch:
    session: AsyncSession
    handler: Handler
    timeout: float
    broken: list[Claimed]  # the call during which the transaction broke, if it does
    done: list[Event] = field(default_factory=list)
    gave_up: list[Event] = field(default_factory=list)

    @property
    def repo(self) -> OutboxRepository:
        return OutboxRepository(self.session)

    async def run(self, limit: int) -> int:
        """Claim, run and settle up to `limit` events; how many were claimed."""
        repo = self.repo
        claimed = [(Event.of(row), n) for row, n in await repo.claim(self.handler.name, limit)]
        if not claimed:  # (a claim skips locked rows: it never waits)
            return 0
        await repo.limit_time(max(1, int(self.timeout * 1000)))
        async with one_notify(self.session):  # the events handlers emit: one NOTIFY
            await self._run(claimed)
        await repo.drop_lanes([e.id for e in self.done], self.handler.name)
        await repo.finish([e.id for e in self.done + self.gave_up])
        return len(claimed)

    async def _run(self, claimed: list[Claimed]) -> None:
        fresh = await self.repo.record_deliveries([e.id for e, _ in claimed], self.handler.name)
        todo = [(e, n) for e, n in claimed if e.id in fresh]
        for event, _ in claimed:
            if event.id not in fresh:  # had it already
                OUTBOX_DISPATCHES.labels(handler=self.handler.name, result="duplicate").inc()
                self.done.append(event)
        mark = after_commit_mark(self.session)
        try:
            async with self.session.begin_nested():
                for index, item in enumerate(todo):
                    outcome = await self._call(item, savepoint=False)
                    if outcome is not Outcome.OK:
                        raise _Failure(index, outcome)
            self._succeeded([event for event, _ in todo])
        except _Failure as failure:  # rolled back: settle it, the rest one by one
            discard_after_commit_since(self.session, mark)
            await self._settle(todo[failure.index])
            rest = todo[: failure.index]
            if failure.outcome is Outcome.TIMED_OUT:
                await self._take_back(todo[failure.index + 1 :])
            else:
                rest += todo[failure.index + 1 :]
            await self._one_by_one(rest)

    async def _one_by_one(self, todo: list[Claimed]) -> None:
        for index, item in enumerate(todo):
            mark = after_commit_mark(self.session)
            outcome = await self._call(item, savepoint=True)
            if outcome is Outcome.OK:
                self._succeeded([item[0]])
                continue
            discard_after_commit_since(self.session, mark)
            await self._settle(item)
            if outcome is Outcome.TIMED_OUT:  # the rest waits for the next batch
                await self._take_back(todo[index + 1 :])
                return

    def _succeeded(self, events: list[Event]) -> None:
        self.done += events
        for _ in events:
            OUTBOX_DISPATCHES.labels(handler=self.handler.name, result="ok").inc()

    async def _settle(self, item: Claimed) -> None:
        """A failed try: its delivery record taken back, the try counted."""
        event, attempts = item
        self.broken[:] = [item]
        await self.repo.unrecord_deliveries([event.id], self.handler.name)
        if await count_failure(self.repo, event, self.handler, attempts + 1):
            self.gave_up.append(event)
        self.broken.clear()

    async def _take_back(self, items: list[Claimed]) -> None:
        """Events not run in this batch: their delivery records go again."""
        await self.repo.unrecord_deliveries([e.id for e, _ in items], self.handler.name)

    async def _call(self, item: Claimed, *, savepoint: bool) -> Outcome:
        """The handler on the event (in a savepoint of its own if asked)."""
        event, handler = item[0], self.handler
        self.broken[:] = [item]
        try:
            async with asyncio.timeout(self.timeout + GRACE_SECONDS):
                if savepoint:
                    async with self.session.begin_nested():
                        await handler.func(self.session, event)
                else:
                    await handler.func(self.session, event)
        except TimeoutError:
            OUTBOX_DISPATCHES.labels(handler=handler.name, result="timeout").inc()
            log_failure("outbox.handler_timeout", event, handler, "TimeoutError")
            return Outcome.TIMED_OUT
        except Exception as exc:
            if is_timeout(exc):  # the database ended a lock wait or a statement
                OUTBOX_DISPATCHES.labels(handler=handler.name, result="timeout").inc()
                log_failure("outbox.handler_timeout", event, handler, type(exc).__name__)
                return Outcome.TIMED_OUT
            OUTBOX_DISPATCHES.labels(handler=handler.name, result="error").inc()
            # Type only: a handler's error message may quote what it was handling.
            log_failure("outbox.handler_failed", event, handler, type(exc).__name__)
            return Outcome.FAILED
        self.broken.clear()
        return Outcome.OK


async def count_failure(
    repo: OutboxRepository, event: Event, handler: Handler, attempts: int
) -> bool:
    """Count a failed try of the event in the handler's lane; True if it gave up."""
    if attempts >= MAX_ATTEMPTS:
        await repo.give_up(event.id, handler.name, attempts)
        report_failed(event, handler, attempts)
        return True
    await repo.retry_later(event.id, handler.name, attempts, retry_wait(attempts))
    return False


def is_timeout(exc: BaseException) -> bool:
    """Postgres' lock_timeout or statement_timeout (SQLSTATE 55P03, 57014)."""
    return db_errors.is_timeout(exc)


def log_failure(message: str, event: Event, handler: Handler, error: str) -> None:
    logger.warning(
        message,
        extra={
            "event_id": str(event.id),
            "type": event.type,
            "handler": handler.name,
            "error": error,
        },
    )


def report_failed(event: Event, handler: Handler, attempts: int) -> None:
    OUTBOX_DISPATCHES.labels(handler=handler.name, result="failed").inc()
    logger.error(
        "outbox.failed",
        extra={
            "event_id": str(event.id),
            "type": event.type,
            "handlers": [handler.name],
            "attempts": attempts,
        },
    )
