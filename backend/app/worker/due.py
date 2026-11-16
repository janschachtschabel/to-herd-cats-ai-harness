"""The worker's due loop (plan M7 decision 1): automations whose term has come fire
here, exactly once across any number of workers, without DBOS.

Every POLL_SECONDS (and at once after a pass that found work) it fires due
automations one per transaction (`automations.firing.fire_next`: the row locked
`FOR UPDATE SKIP LOCKED`, the run or the skip, the log row and the next term
committed together), at most BATCH per pass, so a stop request is seen between
batches. A transaction that fails (a lost connection, a crash before the commit)
leaves the term due as it was: the next pass, here or in another worker, fires it.
A term that fails once it is claimed is set aside for a backoff (`firing.set_aside`,
a transaction of its own; logged with ids and the error's class only, counted in
`herd_automation_terms_set_aside_total`), and the pass goes on with the next term.
Runs it starts are queued; the run loop takes them up like any other.

Each round also takes steps of the daily page review (`wiki/review_pass.py`), one
transaction each, at most REVIEW_STEPS per round: spaces whose pages it has not been
through today (UTC) are claimed `SKIP LOCKED`, their due pages reminded in batches.
A space whose step fails is passed over for the rest of the round. The firing, the
review and the cleanup each run in every round, whatever the others did; the first
error goes on to `serve`, which logs it and waits before the next round.

At most every CLEANUP_EVERY_SECONDS a round also removes, in batches of CLEANUP_BATCH
(one transaction each), what the automations' log no longer needs (`cleanup`): the
events a term took, EVENT_RETENTION after that term, and terms older than
FIRING_RETENTION with their events; never a term whose run is still open, never an
event still waiting for an active rule's quiet time to end. Events waiting with a
deleted rule go, and those a paused rule took in more than EVENT_RETENTION ago. The
same cleanup removes `/mcp`'s call rows (`mcp_call`) older than MCP_CALL_RETENTION,
the files of storage tombstones older than their grace that nothing uses again
(`core/storage_tombstones.py`, plan M9 decision 4), and the rows whose time has run
out (`upkeep.py`: sessions, flows, grants, rate limits; and backups whose process
died). The periods are the
retention catalogue's (`core/retention.py`).

The time comes from a `Clock` (`app.core.clock`); tests set theirs. Only the expiry
upkeep judges at the wall time, as the modules that write those rows do. A task of its own
reads the gauges from the database every METRICS_SECONDS (`automations/metrics.py`:
due automations, the lag of the oldest due term, paused ones by reason, spaces the
review has still to go through today). Up to two database connections at a time.
Outside the worker's readiness, like the run loop.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import SYSTEM_CLOCK, Clock
from app.core.db import Database
from app.core.models_base import utcnow
from app.core.retention import upkeep_after
from app.core.storage import get_storage
from app.core.storage_tombstones import remove_buried
from app.modules.automations.firing import Fired, fire_next, set_aside
from app.modules.automations.metrics import automation_metrics
from app.modules.automations.upkeep_repository import UpkeepRepository
from app.modules.mcp_tools.repository import delete_calls_before
from app.modules.wiki.attachment_files import blob_in_use
from app.modules.wiki.review_pass import Step, review_next
from app.modules.wiki.review_repository import ReviewRepository
from app.worker.upkeep import run_upkeep

logger = logging.getLogger(__name__)

POLL_SECONDS = 5.0
BATCH = 50
REVIEW_STEPS = 20
MAX_ERROR_WAIT_SECONDS = 30.0
METRICS_SECONDS = 10.0
FIRING_RETENTION = upkeep_after("automation_firing")  # terms (with the events they took)
EVENT_RETENTION = upkeep_after("automation_event")  # events a term took, after that term
MCP_CALL_RETENTION = upkeep_after("mcp_call")  # `/mcp`'s call rows
CLEANUP_BATCH = 1000
CLEANUP_EVERY_SECONDS = 60.0


class DueLoop:
    def __init__(
        self,
        database: Database,
        *,
        clock: Clock = SYSTEM_CLOCK,
        cleanup_batch: int = CLEANUP_BATCH,
    ) -> None:
        self.database = database
        self.clock = clock
        self.cleanup_batch = cleanup_batch
        self._last_cleanup: float | None = None
        self.metrics = automation_metrics()  # only processes with a worker export these

    async def serve(self, stop: asyncio.Event) -> None:
        metering = asyncio.create_task(self._metrics_loop(stop))
        try:
            await self._serve(stop)
        finally:
            metering.cancel()
            with suppress(asyncio.CancelledError):
                await metering

    async def _serve(self, stop: asyncio.Event) -> None:
        failures = 0
        while not stop.is_set():
            more = False
            try:
                more = await self.round()
                failures = 0
            except Exception as exc:  # the term stays due; the next pass fires it
                failures += 1
                logger.warning("automations.pass_failed", extra={"error": type(exc).__name__})
            if more:
                continue  # more may be due
            wait = min(2.0**failures, MAX_ERROR_WAIT_SECONDS) if failures else POLL_SECONDS
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=wait)

    async def round(self) -> bool:
        """Fire due automations, then review steps, then the cleanup if due, each
        whatever the others did; whether more may be due. The first error is raised
        once all three had their turn."""
        errors: list[Exception] = []
        fired = await _guarded(self.pass_once(), errors, 0)
        steps = await _guarded(self.review_once(), errors, 0)
        await _guarded(self.cleanup_if_due(), errors, None)
        if errors:
            raise errors[0]
        return fired == BATCH or steps == REVIEW_STEPS

    async def review_once(self) -> int:
        """Steps of the daily page review, one transaction each, until every space is
        checked for today or REVIEW_STEPS were tried; how many were taken. A space
        whose step fails is passed over for the rest of the round."""
        steps, tried, failed = 0, 0, set[uuid.UUID]()
        while tried < REVIEW_STEPS:
            tried += 1
            held: list[uuid.UUID] = []
            try:
                step = await self.review_step(failed, held.append)
            except Exception as exc:
                if not held:
                    raise
                failed.add(held[-1])
                logger.warning(
                    "wiki.review_step_failed",
                    extra={"space_id": str(held[-1]), "error": type(exc).__name__},
                )
                continue
            if step is None:
                break
            steps += 1
        return steps

    async def review_step(
        self,
        skip: set[uuid.UUID] | None = None,
        claimed: Callable[[uuid.UUID], None] | None = None,
    ) -> Step | None:
        async with self.database.session_factory() as session, session.begin():
            step = await review_next(session, self.clock.now(), skip=skip or (), claimed=claimed)
        if step is not None:  # committed
            self.metrics.review_reminders.inc(step.reminded)
        return step

    async def pass_once(self) -> int:
        """Fire due automations, one transaction each, until none is due or BATCH
        were tried (fired or set aside); how many."""
        tried = 0
        while tried < BATCH:
            if not await self.fire_one():
                break
            tried += 1
        return tried

    async def fire_one(self) -> Fired | bool | None:
        """The term fired; True: one failed and was set aside; None: none is due."""
        held: list[tuple[uuid.UUID, datetime]] = []
        try:
            async with self.database.session_factory() as session, session.begin():
                found = await fire_next(
                    session, self.clock.now(), claimed=lambda a, d: held.append((a, d))
                )
        except Exception as exc:
            if not held:
                raise  # nothing claimed (the claim, the connection): `serve` waits
            automation_id, due_at = held[-1]
            logger.warning(
                "automations.term_failed",
                extra={"automation_id": str(automation_id), "error": type(exc).__name__},
            )
            async with self.database.session_factory() as session, session.begin():
                aside = await set_aside(session, automation_id, due_at, self.clock.now())
            if aside:  # committed
                self.metrics.set_aside.inc()
            return True
        if found is not None:  # committed
            self.metrics.firings.labels(outcome=found.label).inc()
        return found

    async def cleanup_if_due(self) -> tuple[int, int, int] | None:
        """`cleanup` at most every CLEANUP_EVERY_SECONDS; None when not yet."""
        now = time.monotonic()
        if self._last_cleanup is not None and now - self._last_cleanup < CLEANUP_EVERY_SECONDS:
            return None
        self._last_cleanup = now
        removed = await self.cleanup()
        await self.remove_buried_files()
        await run_upkeep(  # expiry at the wall time (`upkeep.py`)
            self.database, wall=utcnow(), now=self.clock.now(), limit=self.cleanup_batch
        )
        return removed

    async def cleanup(self) -> tuple[int, int, int]:
        """Remove what the log no longer needs, batch by batch (one transaction each):
        events a term took more than EVENT_RETENTION ago, events waiting with a deleted
        rule or (taken in more than EVENT_RETENTION ago) a paused one, then terms older
        than FIRING_RETENTION; never what an open run may read, never what an active
        rule still waits to fire. Then `/mcp`'s call rows older than MCP_CALL_RETENTION.
        How many terms, events and call rows."""
        now, limit = self.clock.now(), self.cleanup_batch
        events = await self._batches(
            lambda s: UpkeepRepository(s).delete_events_taken_before(now - EVENT_RETENTION, limit)
        )
        events += await self._batches(
            lambda s: UpkeepRepository(s).delete_waiting_of_idle_rules(now - EVENT_RETENTION, limit)
        )
        terms = await self._batches(
            lambda s: UpkeepRepository(s).delete_terms_before(now - FIRING_RETENTION, limit)
        )
        calls = await self._batches(
            lambda s: delete_calls_before(s, now - MCP_CALL_RETENTION, limit)
        )
        return terms, events, calls

    async def remove_buried_files(self) -> int:
        """Remove the files of tombstones older than their grace that no attachment
        uses again, batch by batch (one transaction each); how many files."""
        storage, now, limit = get_storage(), self.clock.now(), self.cleanup_batch
        files = 0
        while True:
            async with self.database.session_factory() as session, session.begin():
                taken, removed = await remove_buried(session, storage, now, blob_in_use, limit)
            files += removed
            if taken < limit:
                return files

    async def _batches(self, step: Callable[[AsyncSession], Awaitable[int]]) -> int:
        removed = 0
        while True:
            async with self.database.session_factory() as session, session.begin():
                count = await step(session)
            removed += count
            if count < self.cleanup_batch:
                return removed

    async def _metrics_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                async with asyncio.timeout(METRICS_SECONDS):
                    await self.update_metrics()
            except Exception as exc:  # the next round tries again
                logger.warning("automations.metrics_failed", extra={"error": type(exc).__name__})
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=METRICS_SECONDS)

    async def update_metrics(self) -> None:
        """The gauges, read from the database at the loop's clock."""
        now = self.clock.now()
        async with self.database.session_factory() as session:
            upkeep = UpkeepRepository(session)
            count, oldest = await upkeep.due(now)
            paused = await upkeep.paused()
            unchecked = await ReviewRepository(session).unchecked(now.astimezone(UTC).date())
        self.metrics.due.set(count)
        lag = (now - oldest).total_seconds() if oldest is not None else 0.0
        self.metrics.oldest_due.set(max(lag, 0.0))
        for reason, n in paused.items():
            self.metrics.paused.labels(reason=reason.value).set(n)
        self.metrics.review_spaces.set(unchecked)


async def _guarded[T](work: Awaitable[T], errors: list[Exception], fallback: T) -> T:
    """`work`'s result; an error is noted in `errors` and `fallback` returned."""
    try:
        return await work
    except Exception as exc:
        errors.append(exc)
        return fallback
