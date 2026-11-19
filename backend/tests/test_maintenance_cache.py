"""Each process holds the maintenance state as a cache (plan M9 decision 9): refreshed
on `NOTIFY herd_maintenance` and at the latest every 5 s; a refresh that fails keeps
what it knew (during a restore the table is locked or not there yet), and turning on
calls what must end at once (the live streams)."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.db import Database
from app.modules.maintenance.cache import INACTIVE, POLL_SECONDS, MaintenanceCache
from app.modules.maintenance.models import MaintenanceReason
from app.modules.maintenance.service import MaintenanceService
from app.modules.maintenance.state import MaintenanceState
from tests.real_db import RealDb

AT = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)
ON = MaintenanceState(active=True, reason=MaintenanceReason.RESTORE, started_at=AT)


async def _until(condition: Callable[[], bool], seconds: float = 5.0) -> None:
    async with asyncio.timeout(seconds):
        while not condition():  # noqa: ASYNC110 -- the cache offers no event for it
            await asyncio.sleep(0.01)


async def test_maintenance_cache_follows_notify_and_polls(real_db: RealDb) -> None:
    assert POLL_SECONDS == 5.0
    database = real_db.database
    listening = MaintenanceCache(poll_seconds=3600)  # only a NOTIFY brings news in time
    polling = MaintenanceCache(poll_seconds=0.2, listen=False)
    stop = asyncio.Event()
    tasks = [
        asyncio.create_task(listening.run(database, stop)),
        asyncio.create_task(polling.run(database, stop)),
    ]
    try:
        await _until(lambda: listening.listening and listening.refreshes >= 1)
        assert not listening.active and not polling.active
        async with database.session_factory() as session:
            await MaintenanceService(session).begin(real_db.org_id, MaintenanceReason.RESTORE, AT)
            await session.commit()
        await _until(lambda: listening.active)
        assert listening.state == ON
        await _until(lambda: polling.active)
        async with database.session_factory() as session:  # no NOTIFY this time
            off = "UPDATE maintenance SET active = false, reason = NULL, started_at = NULL"
            await session.execute(text(off))
            await session.commit()
        await _until(lambda: not polling.active)
        assert listening.active  # nothing told it, and its poll is an hour away
    finally:
        stop.set()
        await asyncio.gather(*tasks)


async def test_a_failed_refresh_keeps_what_the_cache_knew() -> None:
    unreachable = Database("postgresql+asyncpg://herd:herd@127.0.0.1:1/nowhere")
    try:
        cache = MaintenanceCache()
        await cache.refresh(unreachable)
        assert cache.state == INACTIVE
        cache.state = ON
        await cache.refresh(unreachable)
        assert cache.state == ON
    finally:
        await unreachable.dispose()


async def test_turning_on_calls_the_start_hooks_once(real_db: RealDb) -> None:
    calls: list[str] = []
    cache = MaintenanceCache()
    cache.on_start.append(lambda: calls.append("closed"))
    await cache.refresh(real_db.database)
    assert calls == []
    async with real_db.database.session_factory() as session:
        await MaintenanceService(session).begin(real_db.org_id, MaintenanceReason.RESTORE, AT)
        await session.commit()
    await cache.refresh(real_db.database)
    await cache.refresh(real_db.database)
    assert calls == ["closed"]


async def test_a_starting_process_counts_as_in_maintenance_until_it_has_read() -> None:
    """Review M9b F7: a process that starts while a swap holds the tables must not
    serve on what it never read; the first good read decides."""
    unreachable = Database("postgresql+asyncpg://herd:herd@127.0.0.1:1/nowhere")
    cache = MaintenanceCache(poll_seconds=3600, listen=False)
    try:
        await cache.start(unreachable)
        assert cache.active
        assert cache.state.reason is None and cache.state.started_at is None
    finally:
        await cache.stop()
        await unreachable.dispose()


async def test_a_starting_process_serves_once_it_read_no_maintenance(real_db: RealDb) -> None:
    cache = MaintenanceCache(poll_seconds=3600, listen=False)
    try:
        await cache.start(real_db.database)
        assert cache.state == INACTIVE
    finally:
        await cache.stop()
