"""`LISTEN` on one Postgres channel over a connection of its own, outside the pool.

The connection is held for the life of the process; it is checked every
PING_SECONDS and opened again after a loss, with a growing wait. `on_connect` runs
after every (re)connect: notifications sent while no connection listened are lost,
so the owner catches up there. Errors are logged by type only (asyncpg's messages
may quote the connection string).
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress

import asyncpg
from sqlalchemy.engine import URL

logger = logging.getLogger(__name__)

PING_SECONDS = 30.0
PING_TIMEOUT_SECONDS = 5.0
MAX_WAIT_SECONDS = 30.0


def asyncpg_dsn(url: URL) -> str:
    """The SQLAlchemy URL as a DSN for asyncpg itself (password included, escaped)."""
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


class Listener:
    def __init__(
        self,
        url: URL,
        channel: str,
        on_notify: Callable[[str], None],
        on_connect: Callable[[], None] | None = None,
    ) -> None:
        self.url = url
        self.channel = channel
        self.on_notify = on_notify
        self.on_connect = on_connect
        self.connected = False

    async def run(self, stop: asyncio.Event) -> None:
        """Listen until `stop` is set."""
        wait = 1.0
        while not stop.is_set():
            try:
                await self._listen(stop)
                wait = 1.0
            except Exception as exc:
                logger.warning(
                    "listen.connection_lost",
                    extra={"channel": self.channel, "error": type(exc).__name__},
                )
            finally:
                self.connected = False
            if not stop.is_set():
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=wait)
                wait = min(wait * 2, MAX_WAIT_SECONDS)

    async def _listen(self, stop: asyncio.Event) -> None:
        connection = await asyncpg.connect(asyncpg_dsn(self.url))
        try:
            lost = asyncio.Event()
            connection.add_termination_listener(lambda _connection: lost.set())
            await connection.add_listener(
                self.channel, lambda _connection, _pid, _channel, payload: self.on_notify(payload)
            )
            self.connected = True
            if self.on_connect is not None:
                self.on_connect()
            while not stop.is_set() and not lost.is_set():
                with suppress(TimeoutError):
                    await asyncio.wait_for(_first(stop, lost), timeout=PING_SECONDS)
                if not stop.is_set() and not lost.is_set():
                    await asyncio.wait_for(connection.execute("SELECT 1"), PING_TIMEOUT_SECONDS)
            if lost.is_set():
                raise ConnectionError("listen connection closed")
        finally:
            with suppress(Exception):
                await asyncio.wait_for(connection.close(), PING_TIMEOUT_SECONDS)


async def _first(*events: asyncio.Event) -> None:
    """Return as soon as one of `events` is set."""
    waiters = [asyncio.create_task(event.wait()) for event in events]
    try:
        await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for waiter in waiters:
            waiter.cancel()
