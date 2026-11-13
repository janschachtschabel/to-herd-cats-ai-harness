"""The worker: the outbox dispatcher in a loop, driven like the uvicorn servers by the
launcher (`serve`, `should_exit`).

It wakes on `NOTIFY herd_outbox` (sent when a transaction with events commits) and
otherwise every POLL_SECONDS, which also picks up retries that have come due. Setting
`should_exit` (SIGTERM) lets the batch in progress finish, then the loop ends.

`ready` is what the internal `/ready` reports for the worker: the loop runs, its last
pass reached the database, and it finished a batch (or found nothing due) within
STALL_FACTOR handler time limits; a worker stuck longer turns not ready. That moment
is also the gauge `herd_worker_last_pass_timestamp_seconds` (alert HerdWorkerStalled).
The backlog gauges are read from the database every METRICS_SECONDS by a task of
their own, so they stay current while a pass hangs.

Several workers (replicas, or `all` next to a worker) are safe: they claim disjoint
batches. The worker needs up to three database connections at a time (the batch, one
handler's transaction and the metrics query).
"""

import asyncio
import logging
import time
from contextlib import suppress

import app.worker.handlers  # noqa: F401 -- registers every module's handlers
from app.core.config import get_settings
from app.core.db import Database
from app.core.listen import Listener
from app.core.outbox import OUTBOX_CHANNEL
from app.worker.dispatcher import Dispatcher
from app.worker.metrics import worker_metrics

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0
MAX_ERROR_WAIT_SECONDS = 30.0
METRICS_SECONDS = 10.0
STALL_FACTOR = 4  # not ready after this many handler time limits without progress


class Worker:
    def __init__(self, dispatcher: Dispatcher) -> None:
        self.dispatcher = dispatcher
        self.metrics = worker_metrics()  # only processes with a worker export these
        self._running = False
        self._reached_database = False
        self._progress_at: float | None = None  # time.monotonic() of the last progress
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()

    @property
    def stall_seconds(self) -> float:
        return STALL_FACTOR * self.dispatcher.handler_timeout

    @property
    def ready(self) -> bool:
        return (
            self._running
            and self._reached_database
            and self._progress_at is not None
            and time.monotonic() - self._progress_at <= self.stall_seconds
        )

    @property
    def should_exit(self) -> bool:
        return self._stop.is_set()

    @should_exit.setter
    def should_exit(self, value: bool) -> None:
        if value:
            self._stop.set()
            self._wake.set()

    async def serve(self) -> None:
        listener = Listener(
            self.dispatcher.database.engine.url,
            OUTBOX_CHANNEL,
            on_notify=lambda _payload: self._wake.set(),
            on_connect=self._wake.set,  # catch up on what was missed while away
        )
        listening = asyncio.create_task(listener.run(self._stop))
        metering = asyncio.create_task(self._metrics_loop())
        self._running = True
        try:
            await self._loop()
        finally:
            self._running = False
            self._stop.set()
            metering.cancel()
            with suppress(asyncio.CancelledError):
                await listening
            with suppress(asyncio.CancelledError):
                await metering

    async def _loop(self) -> None:
        failures = 0
        while not self._stop.is_set():
            self._wake.clear()
            try:
                await self._pass()
            except Exception as exc:
                failures += 1
                self._reached_database = False
                logger.warning("outbox.pass_failed", extra={"error": type(exc).__name__})
            else:
                failures = 0
                self._reached_database = True
            wait = min(2.0**failures, MAX_ERROR_WAIT_SECONDS) if failures else POLL_SECONDS
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=wait)

    async def _pass(self) -> None:
        """Batches until one is short (nothing more is due) or the worker stops."""
        while not self._stop.is_set():
            count = await self.dispatcher.dispatch_batch()
            self._progressed()
            if count < self.dispatcher.batch_size:
                break
        await self.dispatcher.cleanup_if_due()

    def _progressed(self) -> None:
        self._progress_at = time.monotonic()
        self.metrics.last_pass.set(time.time())

    async def _metrics_loop(self) -> None:
        while True:
            try:
                async with asyncio.timeout(METRICS_SECONDS):
                    await self.dispatcher.update_metrics()
            except Exception as exc:  # the next round tries again
                logger.warning("outbox.metrics_failed", extra={"error": type(exc).__name__})
            await asyncio.sleep(METRICS_SECONDS)


def create_worker(database: Database) -> Worker:
    """The worker with every registered handler (`app.worker.registry.REGISTRY`)."""
    timeout = get_settings().worker_handler_timeout_seconds
    return Worker(Dispatcher(database, handler_timeout=timeout))
