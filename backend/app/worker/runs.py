"""The worker's agent runs (plan M5 task 6, decision 1): a loop of its own next to the
outbox lanes, not part of the worker's readiness (a slow provider must not make the
worker look stuck; hung runs have their own gauge and alert).

- Up to `HERD_RUN_CONCURRENCY` runs at a time per worker, each a task; a free place
  claims the next run (`executor_repository.claim`: the connection's
  `max_concurrency` across workers, one run per conversation). New messages wake the
  loop through the outbox's NOTIFY (`wake`); otherwise it looks every POLL_SECONDS.
- One renewal task extends the lease of every run this worker holds every third of
  `HERD_RUN_LEASE_SECONDS`. A run whose lease another worker took over (this one hung
  longer than the lease) is cancelled here; the other worker starts it again.
- Stopping cancels the runs in progress; their leases run out and another worker
  starts them again (level 1 writes nothing but its answer, which is written once).

Database connections: one at a time per run in progress (each step's short
transaction, never during a provider call), plus one each for claiming, renewing and
the gauges: at most `HERD_RUN_CONCURRENCY` + 3 per worker.
"""

import asyncio
import logging
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass

from prometheus_client import Counter, Gauge, Histogram

from app.core.db import Database
from app.core.metrics import REGISTRY
from app.modules.agents.executor import Executor
from app.modules.agents.executor_repository import Claimed, claim, open_runs, renew
from app.modules.agents.step_host import units_of

logger = logging.getLogger(__name__)

POLL_SECONDS = 1.0
METRICS_SECONDS = 10.0
MAX_ERROR_WAIT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class RunMetrics:
    finished: Counter
    duration: Histogram
    queued: Gauge
    oldest_queued: Gauge
    stuck: Gauge


_metrics: RunMetrics | None = None


def run_metrics() -> RunMetrics:
    """Registered by the first run loop of a process (an API process exports none)."""
    global _metrics  # noqa: PLW0603 -- one registration per process
    if _metrics is None:
        _metrics = RunMetrics(
            finished=Counter(
                "herd_runs_total",
                "Agent runs finished by this worker, by stop reason.",
                ["reason"],
                registry=REGISTRY,
            ),
            duration=Histogram(
                "herd_run_duration_seconds",
                "Duration of agent runs (one attempt) in this worker.",
                buckets=(1, 2.5, 5, 10, 30, 60, 120, 300, 600),
                registry=REGISTRY,
            ),
            queued=Gauge(
                "herd_runs_queued",
                "Agent runs waiting for a worker (from the database).",
                registry=REGISTRY,
                multiprocess_mode="livemax",
            ),
            oldest_queued=Gauge(
                "herd_runs_oldest_queued_seconds",
                "Age of the oldest waiting agent run (0 without one; from the database).",
                registry=REGISTRY,
                multiprocess_mode="livemax",
            ),
            stuck=Gauge(
                "herd_runs_stuck",
                "Agent runs running with a lease no worker renews, or for longer than any "
                "run may (from the database).",
                registry=REGISTRY,
                multiprocess_mode="livemax",
            ),
        )
    return _metrics


class RunLoop:
    def __init__(
        self,
        database: Database,
        *,
        concurrency: int,
        lease: float,
        executor: Executor | None = None,
    ) -> None:
        self.database = database
        self.concurrency = concurrency
        self.lease = lease
        self.executor = executor or Executor(units_of(database.session_factory))
        self.metrics = run_metrics()
        self.wake = asyncio.Event()
        self.held: dict[uuid.UUID, tuple[int, asyncio.Task[None]]] = {}

    async def serve(self, stop: asyncio.Event) -> None:
        renewing = asyncio.create_task(self._renew_loop(stop))
        metering = asyncio.create_task(self._metrics_loop(stop))
        failures = 0
        try:
            while not stop.is_set():
                self.wake.clear()
                try:
                    while len(self.held) < self.concurrency and not stop.is_set():
                        claimed = await self.claim()
                        if claimed is None:
                            break
                        self._start(claimed)
                    failures = 0
                except Exception as exc:
                    failures += 1
                    logger.warning("runs.claim_failed", extra={"error": type(exc).__name__})
                wait = min(2.0**failures, MAX_ERROR_WAIT_SECONDS) if failures else POLL_SECONDS
                with suppress(TimeoutError):
                    await asyncio.wait_for(self._woken(stop), timeout=wait)
        finally:
            tasks = [renewing, metering, *(task for _, task in self.held.values())]
            for task in tasks:
                task.cancel()
            for task in tasks:
                with suppress(asyncio.CancelledError):
                    await task

    async def claim(self) -> Claimed | None:
        async with self.database.session_factory() as session, session.begin():
            return await claim(session, self.lease)

    def _start(self, claimed: Claimed) -> None:
        task = asyncio.create_task(self._work(claimed))
        self.held[claimed.id] = (claimed.attempt, task)

    async def _work(self, claimed: Claimed) -> None:
        started = time.monotonic()
        try:
            reason = await self.executor.execute(claimed)
            if reason is not None:
                self.metrics.finished.labels(reason=reason.value).inc()
                self.metrics.duration.observe(time.monotonic() - started)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # the lease runs out; another attempt follows
            error = type(exc).__name__
            logger.warning("runs.failed", extra={"run_id": str(claimed.id), "error": error})
        finally:
            current = self.held.get(claimed.id)
            if current is not None and current[0] == claimed.attempt:
                del self.held[claimed.id]
            self.wake.set()

    async def _woken(self, stop: asyncio.Event) -> None:
        waits = [asyncio.create_task(self.wake.wait()), asyncio.create_task(stop.wait())]
        try:
            await asyncio.wait(waits, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in waits:
                task.cancel()

    async def _renew_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self.lease / 3)
            await self.renew_once()

    async def renew_once(self) -> None:
        held = {run_id: attempt for run_id, (attempt, _) in self.held.items()}
        if not held:
            return
        try:
            async with self.database.session_factory() as session, session.begin():
                kept = await renew(session, held, self.lease)
        except Exception as exc:  # the next round tries again, before the lease ends
            logger.warning("runs.renew_failed", extra={"error": type(exc).__name__})
            return
        for run_id in set(held) - kept:
            current = self.held.get(run_id)
            if current is not None and current[0] == held[run_id]:
                current[1].cancel()  # another worker has it now

    async def _metrics_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                async with asyncio.timeout(METRICS_SECONDS):
                    await self.update_metrics()
            except Exception as exc:  # the next round tries again
                logger.warning("runs.metrics_failed", extra={"error": type(exc).__name__})
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=METRICS_SECONDS)

    async def update_metrics(self) -> None:
        async with self.database.session_factory() as session:
            queued, oldest, stuck = await open_runs(session)
        self.metrics.queued.set(queued)
        self.metrics.oldest_queued.set(oldest)
        self.metrics.stuck.set(stuck)
