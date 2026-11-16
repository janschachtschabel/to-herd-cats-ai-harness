"""What each process knows about maintenance (plan M9 decision 9): a cache, read again
on `NOTIFY herd_maintenance` (`listen.py`, also after every reconnect) and at the
latest every POLL_SECONDS. The middleware, the collab relay, the internal collab API
and the worker's loops ask it, never the database: during a restore the tables are
locked or not there yet.

A refresh that fails (the database is locked, unreachable, or has no table yet) keeps
what the cache knew, so maintenance that was on stays on until a read says otherwise.
Turning on calls `on_start` (the public app ends its live streams there; browsers
reconnect and get 503). One cache per process (`maintenance_cache()`): whatever runs
in it (the public app, the worker) starts and stops it, and it runs while any of
them does.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress

from app.core.db import Database
from app.core.listen import Listener
from app.modules.maintenance.repository import CHANNEL, MaintenanceRepository
from app.modules.maintenance.state import INACTIVE

__all__ = ["INACTIVE", "POLL_SECONDS", "MaintenanceCache", "in_maintenance", "maintenance_cache"]

logger = logging.getLogger(__name__)

POLL_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 2.0


class MaintenanceCache:
    def __init__(self, *, poll_seconds: float = POLL_SECONDS, listen: bool = True) -> None:
        self.state = INACTIVE
        self.poll_seconds = poll_seconds
        self.listen = listen
        self.on_start: list[Callable[[], None]] = []
        self.refreshes = 0  # successful reads
        self._listener: Listener | None = None
        self._wake = asyncio.Event()
        self._users = 0
        self._stop: asyncio.Event | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def active(self) -> bool:
        return self.state.active

    @property
    def listening(self) -> bool:
        return self._listener is not None and self._listener.connected

    async def refresh(self, database: Database) -> None:
        try:
            async with asyncio.timeout(READ_TIMEOUT_SECONDS):
                async with database.session_factory() as session:
                    state = await MaintenanceRepository(session).current()
        except Exception as exc:  # locked, unreachable, no table yet: keep what we knew
            logger.warning("maintenance.refresh_failed", extra={"error": type(exc).__name__})
            return
        turned_on = state.active and not self.state.active
        if state.active != self.state.active:
            logger.warning("maintenance.changed", extra={"active": state.active})
        self.state = state
        self.refreshes += 1
        if turned_on:
            for hook in list(self.on_start):
                hook()

    async def run(self, database: Database, stop: asyncio.Event) -> None:
        """Refresh until `stop` is set: woken by a NOTIFY, else every poll."""
        listening: asyncio.Task[None] | None = None
        if self.listen:
            self._listener = Listener(
                database.engine.url,
                CHANNEL,
                on_notify=lambda _payload: self._wake.set(),
                on_connect=self._wake.set,  # a NOTIFY may have been missed meanwhile
            )
            listening = asyncio.create_task(self._listener.run(stop))
        try:
            while not stop.is_set():
                self._wake.clear()
                await self.refresh(database)
                await _first_of(stop, self._wake, within=self.poll_seconds)
        finally:
            if listening is not None:
                listening.cancel()
                with suppress(asyncio.CancelledError):
                    await listening

    async def start(self, database: Database) -> None:
        """Run while any user of this process does; the state is read once first."""
        self._users += 1
        if self._task is None:
            self._stop = asyncio.Event()
            await self.refresh(database)
            self._task = asyncio.create_task(self.run(database, self._stop))

    async def stop(self) -> None:
        self._users = max(self._users - 1, 0)
        if self._users or self._task is None or self._stop is None:
            return
        self._stop.set()
        task, self._task = self._task, None
        await task


async def _first_of(*events: asyncio.Event, within: float) -> None:
    """Return once one of `events` is set, or after `within` seconds."""
    waiters = [asyncio.create_task(event.wait()) for event in events]
    try:
        await asyncio.wait(waiters, timeout=within, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for waiter in waiters:
            waiter.cancel()


_CACHE = MaintenanceCache()


def maintenance_cache() -> MaintenanceCache:
    """The process's cache."""
    return _CACHE


def in_maintenance() -> bool:
    """Whether this process knows the installation to be in maintenance."""
    return _CACHE.active
