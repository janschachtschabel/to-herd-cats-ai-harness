"""`Listener`: LISTEN on a connection of its own; after the connection is lost it
connects again and says so (`on_connect`), so its owner can catch up."""

import asyncio

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.listen import Listener, asyncpg_dsn

CHANNEL = "herd_test_listen"


async def _until(predicate, seconds: float = 10.0) -> None:  # type: ignore[no-untyped-def]  # noqa: ASYNC109
    async with asyncio.timeout(seconds):
        while not predicate():  # noqa: ASYNC110 -- waits on another task's callbacks
            await asyncio.sleep(0.02)


async def test_listener_receives_and_comes_back_after_a_lost_connection() -> None:
    url = make_url(get_settings().test_database_url)
    received: list[str] = []
    connects: list[int] = []
    listener = Listener(url, CHANNEL, received.append, lambda: connects.append(1))
    stop = asyncio.Event()
    task = asyncio.create_task(listener.run(stop))
    other = await asyncpg.connect(asyncpg_dsn(url))
    try:
        await _until(lambda: listener.connected and connects)
        await other.execute(f"NOTIFY {CHANNEL}, 'eins'")
        await _until(lambda: received == ["eins"])

        terminated = await other.fetchval(
            "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity"
            " WHERE pid <> pg_backend_pid() AND query = $1",
            f'LISTEN "{CHANNEL}"',
        )
        assert terminated == 1
        await _until(lambda: len(connects) == 2 and listener.connected)
        await other.execute(f"NOTIFY {CHANNEL}, 'zwei'")
        await _until(lambda: received == ["eins", "zwei"])
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=10)
        await other.close()
    assert listener.connected is False


async def test_every_loss_after_a_healthy_connection_reconnects_after_the_first_wait() -> None:
    """The wait grows only while connecting fails; a connection that listened resets
    it, so the fifth loss in a row costs about a second like the first (review N2)."""
    url = make_url(get_settings().test_database_url)
    connects: list[float] = []
    loop = asyncio.get_running_loop()
    listener = Listener(url, CHANNEL, lambda _payload: None, lambda: connects.append(loop.time()))
    stop = asyncio.Event()
    task = asyncio.create_task(listener.run(stop))
    other = await asyncpg.connect(asyncpg_dsn(url))
    try:
        await _until(lambda: listener.connected and connects)
        for loss in range(1, 6):
            lost_at = loop.time()
            await other.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                " WHERE pid <> pg_backend_pid() AND query = $1",
                f'LISTEN "{CHANNEL}"',
            )
            await _until(lambda n=loss: len(connects) == n + 1 and listener.connected, 15.0)
            assert connects[-1] - lost_at < 2.5, f"loss {loss}: {connects[-1] - lost_at:.1f} s"
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=10)
        await other.close()
