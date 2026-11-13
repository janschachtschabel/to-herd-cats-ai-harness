"""The worker: the outbox dispatcher in a loop, driven like the uvicorn servers by the
launcher (`serve`, `should_exit`).

It wakes on `NOTIFY herd_outbox` (sent when a transaction with events commits) and
otherwise every POLL_SECONDS, which also picks up retries that have come due. Setting
`should_exit` (SIGTERM) lets the batch in progress finish, then the loop ends.
`ready` is what the internal `/ready` reports for the worker: the loop runs and its
last pass reached the database.

Several workers (replicas, or `all` next to a worker) are safe: they claim disjoint
batches. The worker needs two database connections at a time (the batch and one
handler's transaction).
"""

import asyncio
import logging
from contextlib import suppress

from app.core.db import Database
from app.core.listen import Listener
from app.core.outbox import OUTBOX_CHANNEL
from app.worker.dispatcher import Dispatcher

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0
MAX_ERROR_WAIT_SECONDS = 30.0


class Worker:
    def __init__(self, dispatcher: Dispatcher) -> None:
        self.dispatcher = dispatcher
        self.ready = False
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()

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
        try:
            await self._loop()
        finally:
            self.ready = False
            self._stop.set()
            with suppress(asyncio.CancelledError):
                await listening

    async def _loop(self) -> None:
        failures = 0
        while not self._stop.is_set():
            self._wake.clear()
            try:
                await self._pass()
            except Exception as exc:
                failures += 1
                self.ready = False
                logger.warning("outbox.pass_failed", extra={"error": type(exc).__name__})
            else:
                failures = 0
                self.ready = True
            wait = min(2.0**failures, MAX_ERROR_WAIT_SECONDS) if failures else POLL_SECONDS
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=wait)

    async def _pass(self) -> None:
        """Batches until one is short (nothing more is due) or the worker stops."""
        while not self._stop.is_set():
            if await self.dispatcher.dispatch_batch() < self.dispatcher.batch_size:
                break
        await self.dispatcher.cleanup_if_due()
        await self.dispatcher.update_metrics()


def create_worker(database: Database) -> Worker:
    """The worker with every registered handler (`app.worker.registry.REGISTRY`)."""
    return Worker(Dispatcher(database))
