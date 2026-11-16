"""The worker: the outbox dispatcher in loops, driven like the uvicorn servers by the
launcher (`serve`, `should_exit`).

One loop routes new events into lanes (`Dispatcher.route`) and keeps the table clean;
every handler has a loop of its own that works off its lane (`dispatch_lane`), so the
handlers never wait for each other (review M4 P3). The router wakes on
`NOTIFY herd_outbox` (sent when a transaction with events commits) and otherwise
every POLL_SECONDS; it wakes the lanes it routed events into, and each lane also
looks every POLL_SECONDS (for retries that have come due). Setting `should_exit`
(SIGTERM) lets the batches in progress finish, then the loops end.

`ready` is what the internal `/ready` reports for the worker: the loops run, the last
pass of each reached the database, and each finished a batch (or found nothing due)
within STALL_FACTOR handler time limits; a loop stuck longer turns the worker not
ready. The oldest of those moments is also the gauge
`herd_worker_last_pass_timestamp_seconds` (alert HerdWorkerStalled). The backlog
gauges are read from the database every METRICS_SECONDS by a task of their own, so
they stay current while a pass hangs.

Several workers (replicas, or `all` next to a worker) are safe: they route and claim
disjoint rows. The worker needs up to one database connection per handler, one for
routing and one for the metrics query at a time.

Agent runs (`runs.py`) have a loop of their own beside these, outside `ready`; the
outbox's NOTIFY wakes it too (a new message to an agent commits with an event). It
adds up to `HERD_RUN_CONCURRENCY` + 3 database connections. Automations that come
due fire in the due loop (`due.py`), also outside `ready`, with up to two connections
(firing, gauges). An owner's "Jetzt sichern" is taken up by a loop of its own
(`modules/backups/jobs.py`), also outside `ready`, with up to two connections while a
backup runs.

In maintenance (plan M9 decision 9) the loops pause: the process's maintenance cache
(`modules/maintenance/cache.py`), which the worker runs, tells them; a paused pass
counts as progress, so the worker stays ready.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress

import app.worker.handlers  # noqa: F401 -- registers every module's handlers
from app.core.config import get_settings
from app.core.db import Database
from app.core.listen import Listener
from app.core.outbox import OUTBOX_CHANNEL
from app.modules.backups.jobs import BackupJobLoop
from app.modules.backups.metrics import update_backup_metrics
from app.modules.maintenance.cache import maintenance_cache
from app.worker.dispatcher import Dispatcher
from app.worker.due import DueLoop
from app.worker.metrics import worker_metrics
from app.worker.registry import Handler
from app.worker.runs import RunLoop

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0
MAX_ERROR_WAIT_SECONDS = 30.0
METRICS_SECONDS = 10.0
STALL_FACTOR = 4  # not ready after this many handler time limits without progress
ROUTER = "route"  # the routing loop's name (handlers have theirs)


class _Loop:
    """One loop's state: woken by `wake`, last progress (monotonic and wall clock)."""

    def __init__(self) -> None:
        self.wake = asyncio.Event()
        self.reached_database = False
        self.progress_at: float | None = None
        self.progress_wall = 0.0


class Worker:
    def __init__(
        self,
        dispatcher: Dispatcher,
        runs: RunLoop | None = None,
        due: DueLoop | None = None,
        backups: BackupJobLoop | None = None,
    ) -> None:
        self.dispatcher = dispatcher
        self.runs = runs
        self.due = due
        self.backups = backups
        self.metrics = worker_metrics()  # only processes with a worker export these
        self._running = False
        self._stop = asyncio.Event()
        self._loops = {ROUTER: _Loop()} | {h.name: _Loop() for h in dispatcher.handlers}

    @property
    def stall_seconds(self) -> float:
        return STALL_FACTOR * self.dispatcher.handler_timeout

    @property
    def ready(self) -> bool:
        now = time.monotonic()
        return self._running and all(
            loop.reached_database
            and loop.progress_at is not None
            and now - loop.progress_at <= self.stall_seconds
            for loop in self._loops.values()
        )

    @property
    def should_exit(self) -> bool:
        return self._stop.is_set()

    @should_exit.setter
    def should_exit(self, value: bool) -> None:
        if value:
            self._stop.set()
            for loop in self._loops.values():
                loop.wake.set()

    async def serve(self) -> None:
        cache = maintenance_cache()  # the loops pause while it says maintenance
        await cache.start(self.dispatcher.database)
        try:
            await self._serve()
        finally:
            await cache.stop()

    async def _serve(self) -> None:
        listener = Listener(
            self.dispatcher.database.engine.url,
            OUTBOX_CHANNEL,
            on_notify=lambda _payload: self._woken(),
            on_connect=self._woken,  # catch up on what was missed while away
        )
        listening = asyncio.create_task(listener.run(self._stop))
        metering = asyncio.create_task(self._metrics_loop())
        running = asyncio.create_task(self.runs.serve(self._stop)) if self.runs else None
        firing = asyncio.create_task(self.due.serve(self._stop)) if self.due else None
        backing = asyncio.create_task(self.backups.serve(self._stop)) if self.backups else None
        loops = [asyncio.create_task(self._loop(ROUTER, self._route_pass))]
        for handler in self.dispatcher.handlers:
            loops.append(asyncio.create_task(self._loop(handler.name, self._lane_pass(handler))))
        self._running = True
        try:
            await asyncio.gather(*loops)
        finally:
            self._running = False
            self._stop.set()
            metering.cancel()
            for task in loops:
                task.cancel()
            extra = [task for task in (running, firing, backing) if task is not None]
            for task in (listening, metering, *loops, *extra):
                with suppress(asyncio.CancelledError):
                    await task

    def _woken(self) -> None:
        self._loops[ROUTER].wake.set()
        if self.runs is not None:
            self.runs.wake.set()

    async def _loop(self, name: str, one_pass: Callable[[], Awaitable[None]]) -> None:
        loop, failures = self._loops[name], 0
        while not self._stop.is_set():
            loop.wake.clear()
            try:
                await one_pass()
            except Exception as exc:
                failures += 1
                loop.reached_database = False
                logger.warning(
                    "outbox.pass_failed", extra={"loop": name, "error": type(exc).__name__}
                )
            else:
                failures = 0
                loop.reached_database = True
            wait = min(2.0**failures, MAX_ERROR_WAIT_SECONDS) if failures else POLL_SECONDS
            with suppress(TimeoutError):
                await asyncio.wait_for(loop.wake.wait(), timeout=wait)

    async def _route_pass(self) -> None:
        """Batches until one is short (nothing more is new) or the worker stops; then
        the lanes that got rows are woken."""
        woken: set[str] = set()
        while not self._stop.is_set():
            routed = await self.dispatcher.route()
            woken |= routed.lanes
            self._progressed(ROUTER)
            if routed.events < self.dispatcher.route_batch:
                break
        for name in woken:
            self._loops[name].wake.set()
        await self.dispatcher.cleanup_if_due()

    def _lane_pass(self, handler: Handler) -> Callable[[], Awaitable[None]]:
        async def one_pass() -> None:
            """Batches until one is short (nothing more is due) or the worker stops."""
            while not self._stop.is_set():
                count = await self.dispatcher.dispatch_lane(handler)
                self._progressed(handler.name)
                if count < self.dispatcher.batch_size:
                    break

        return one_pass

    def _progressed(self, name: str) -> None:
        loop = self._loops[name]
        loop.progress_at, loop.progress_wall = time.monotonic(), time.time()
        if all(other.progress_at is not None for other in self._loops.values()):
            self.metrics.last_pass.set(min(other.progress_wall for other in self._loops.values()))

    async def _metrics_loop(self) -> None:
        while True:
            try:
                async with asyncio.timeout(METRICS_SECONDS):
                    await self.dispatcher.update_metrics()
            except Exception as exc:  # the next round tries again
                logger.warning("outbox.metrics_failed", extra={"error": type(exc).__name__})
            try:  # the backups' gauges (plan M9 decision 11), from backup_run
                async with asyncio.timeout(METRICS_SECONDS):
                    await update_backup_metrics(self.dispatcher.database, get_settings())
            except Exception as exc:
                logger.warning("backup.metrics_failed", extra={"error": type(exc).__name__})
            await asyncio.sleep(METRICS_SECONDS)


def create_worker(database: Database) -> Worker:
    """The worker with every registered handler (`app.worker.registry.REGISTRY`)."""
    settings = get_settings()
    timeout = settings.worker_handler_timeout_seconds
    runs = RunLoop(database, concurrency=settings.run_concurrency, lease=settings.run_lease_seconds)
    dispatcher = Dispatcher(database, handler_timeout=timeout)
    return Worker(dispatcher, runs, DueLoop(database), BackupJobLoop(database))
