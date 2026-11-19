"""The worker takes up an owner's "Jetzt sichern" (plan M9 task 13): the request row
becomes the backup (archive, `ok`), one backup at a time, never in maintenance; until
a worker takes it up within REQUEST_GRACE neither another backup nor the upkeep counts
it as dead; the owners hear of every change (`backup.changed`, ids only)."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.core.clock import SYSTEM_CLOCK
from app.core.config import Settings, get_settings
from app.core.listen import asyncpg_dsn
from app.core.migrations import SchemaState
from app.modules.backups.jobs import BackupJobLoop
from app.modules.backups.models import BackupRun, BackupState, BackupTrigger
from app.modules.backups.repository import (
    REQUEST_GRACE,
    BackupRunRepository,
    hold_backup_lock,
    release_backup_lock,
)
from app.modules.messaging.live_decode import decode
from app.modules.messaging.live_events import LIVE_CHANNEL
from app.modules.users.models import User
from app.ops import backup as backup_module
from app.ops.backup import create_backup
from tests.factories_restore import source_settings
from tests.real_db import RealDb


@pytest.fixture
def settings(tmp_path: Path, data_dir: Path) -> Settings:
    return source_settings(tmp_path, data_dir)


@pytest.fixture
async def heard(real_db: RealDb) -> AsyncIterator[list[str]]:
    """The payloads of `herd_live` while the test runs."""
    payloads: list[str] = []
    url = make_url(get_settings().test_database_url)
    connection = await asyncpg.connect(asyncpg_dsn(url))
    await connection.add_listener(LIVE_CHANNEL, lambda *args: payloads.append(args[3]))
    try:
        yield payloads
    finally:
        await connection.close()


async def _request(real_db: RealDb, minutes_ago: float = 0) -> BackupRun:
    async with real_db.database.session_factory() as session, session.begin():
        at = SYSTEM_CLOCK.now() - timedelta(minutes=minutes_ago)
        run = await BackupRunRepository(session).start(real_db.org_id, BackupTrigger.ADMIN, at)  # type: ignore[arg-type]
    return run


async def _row(real_db: RealDb, run_id: object) -> BackupRun:
    async with real_db.database.session_factory() as session:
        run = await session.get(BackupRun, run_id)
        assert run is not None
        return run


def _loop(real_db: RealDb, settings: Settings, paused: bool = False) -> BackupJobLoop:
    return BackupJobLoop(real_db.database, settings=lambda: settings, paused=lambda: paused)


async def test_the_worker_takes_an_owners_request_up(
    real_db: RealDb, settings: Settings, heard: list[str]
) -> None:
    request = await _request(real_db)
    assert await _loop(real_db, settings).once() == BackupState.OK
    run = await _row(real_db, request.id)
    assert (run.trigger, run.state, run.offsite_state) == (BackupTrigger.ADMIN, "ok", "off")
    assert run.archive is not None and (settings.backup_dir / run.archive).is_file()
    async with real_db.database.session_factory() as session:
        assert len((await session.scalars(select(BackupRun))).all()) == 1  # no second row
        owner = await session.scalar(select(User.id).where(User.email == real_db.owner_email))
    await asyncio.sleep(0.2)  # the notifications arrive after their commits
    events = [decode(p) for p in heard]
    told = [(e.name, e.user_id, e.backup_id) for e in events if e is not None]
    assert told and set(told) == {("backup.changed", owner, request.id)}
    assert all(set(json.loads(p)) <= {"t", "o", "c", "m", "p", "u", "b"} for p in heard)
    assert await _loop(real_db, settings).once() is None  # nothing waits any more


async def test_a_request_waits_while_another_backup_runs_and_in_maintenance(
    real_db: RealDb, settings: Settings
) -> None:
    request = await _request(real_db)
    assert await _loop(real_db, settings, paused=True).once() is None
    async with real_db.database.engine.connect() as holder:
        assert await hold_backup_lock(holder)
        assert await _loop(real_db, settings).once() is None
        await release_backup_lock(holder)
    assert (await _row(real_db, request.id)).state == BackupState.RUNNING
    assert await _loop(real_db, settings).once() == BackupState.OK


async def test_only_a_young_request_is_spared(real_db: RealDb, settings: Settings) -> None:
    young = await _request(real_db)
    other = await create_backup(settings, trigger=BackupTrigger.CLI, clock=SYSTEM_CLOCK)
    assert other.state == BackupState.OK  # another backup ran meanwhile
    assert (await _row(real_db, young.id)).state == BackupState.RUNNING
    now = SYSTEM_CLOCK.now()
    async with real_db.database.session_factory() as session, session.begin():
        assert await BackupRunRepository(session).interrupt_dead(now) == 0
    assert (await _row(real_db, young.id)).state == BackupState.RUNNING
    async with real_db.database.session_factory() as session, session.begin():
        later = now + REQUEST_GRACE + timedelta(seconds=1)
        assert await BackupRunRepository(session).interrupt_dead(later) == 1
    gone = await _row(real_db, young.id)
    assert (gone.state, gone.error_code) == (BackupState.INTERRUPTED, "backup.interrupted")

    old = await _request(real_db, minutes_ago=REQUEST_GRACE.total_seconds() / 60 + 1)
    assert await _loop(real_db, settings).once() is None  # too old to take up
    restored = await _request(real_db)
    async with real_db.database.session_factory() as session, session.begin():
        runs = BackupRunRepository(session)  # a restore spares none (`finish_restore`)
        after = SYSTEM_CLOCK.now() + timedelta(seconds=1)
        assert await runs.interrupt_running(after, started_before=after) == 2
    assert {(await _row(real_db, r.id)).state for r in (old, restored)} == {"interrupted"}


async def test_a_request_refused_before_it_began_fails_with_the_code(
    real_db: RealDb, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def behind(engine: object) -> SchemaState:
        return SchemaState.BEHIND

    monkeypatch.setattr(backup_module, "schema_state", behind)
    request = await _request(real_db)
    assert await _loop(real_db, settings).once() == BackupState.FAILED
    run = await _row(real_db, request.id)
    assert (run.state, run.error_code) == (BackupState.FAILED, "backup.schema_behind")
    assert run.finished_at is not None
