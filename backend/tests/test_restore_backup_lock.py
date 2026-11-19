"""A restore and the backups (module review M9a re-check, P1).

`finish_restore` marks the archive's own run (it was `running` in its snapshot) with
the exempt code `backup.in_restored_archive`. A backup alive on the restored database
must not get that code: its death would never count (HerdBackupFailing silent), and a
backup marking the archive's row `backup.interrupted` would be a false failure. So:

- a restore holds the backup lock for its whole duration and is refused with
  `restore.backup_running` while a backup holds it;
- `finish_restore` marks only rows started at or before the archive's time (the
  manifest's `created_at`, whole seconds); any other `running` row is left to whoever
  holds the backup lock later.
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import make_engine
from app.modules.backups.models import BackupRun, BackupState, BackupTrigger
from app.modules.backups.repository import (
    BackupRunRepository,
    hold_backup_lock,
    release_backup_lock,
)
from app.ops import restore as restore_module
from app.ops.restore import RestoreRefused, restore_into_empty
from app.ops.restore_after import finish_restore
from tests.factories_restore import Target, make_archive, source_settings
from tests.real_db import RealDb
from tests.support.clock import SettableClock

ARCHIVE_AT = datetime(2026, 11, 15, 2, 30, 7, tzinfo=UTC)
AT = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)


async def _running(real_db: RealDb, started_at: datetime) -> uuid.UUID:
    async with real_db.database.session_factory() as s:
        run = BackupRun(
            org_id=real_db.org_id,
            trigger=BackupTrigger.SCHEDULE,
            state=BackupState.RUNNING,
            started_at=started_at,
        )
        s.add(run)
        await s.commit()
        return run.id


async def test_finish_restore_leaves_the_row_of_a_backup_started_after_the_archive(
    real_db: RealDb,
) -> None:
    # The archive's own run started within the archive's second (the manifest keeps
    # whole seconds); a backup on the restored database started later.
    own = await _running(real_db, ARCHIVE_AT + timedelta(microseconds=420_000))
    live = await _running(real_db, AT - timedelta(minutes=1))
    async with real_db.database.session_factory() as s:
        await finish_restore(
            s,
            archive_name="herd-20261115T023007Z-1.0.0.tar",
            archive_created_at=ARCHIVE_AT,
            revision_from="x",
            revision_to="x",
            clock=SettableClock(AT),
        )
        await s.commit()
        rows = {
            r.id: (r.state, r.error_code)
            for r in await s.execute(select(BackupRun.id, BackupRun.state, BackupRun.error_code))
        }
    assert rows[own] == (BackupState.INTERRUPTED, "backup.in_restored_archive")
    assert rows[live] == (BackupState.RUNNING, None)

    # The live backup dies later: whoever holds the backup lock marks it, and it counts.
    async with real_db.database.session_factory() as s:
        await BackupRunRepository(s).interrupt_running(AT + timedelta(hours=1))
        await s.commit()
        figures = await BackupRunRepository(s).figures()
    assert figures.last_failed == AT + timedelta(hours=1)


async def test_a_restore_is_refused_while_a_backup_runs(
    real_db: RealDb, target: Target, tmp_path: Path, data_dir: Path
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    engine = make_engine(target.settings.database())
    try:
        async with engine.connect() as holder:
            assert await hold_backup_lock(holder)
            with pytest.raises(RestoreRefused) as refused:
                await restore_into_empty(
                    target.settings, archive, without_secrets=False, clock=SettableClock(AT)
                )
            await release_backup_lock(holder)
    finally:
        await engine.dispose()
    assert refused.value.problems == ["restore.backup_running"]
    assert await target.tables() == {}
    assert target.files() == {}


async def test_a_restore_holds_the_backup_lock_while_it_runs(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    restore_database = restore_module._restore_database
    seen: list[bool] = []

    async def restore_and_try_a_backup(settings: Settings, path: Path) -> None:
        await restore_database(settings, path)
        engine = make_engine(settings.database())
        try:
            async with engine.connect() as other:
                taken = await hold_backup_lock(other)
                if taken:
                    await release_backup_lock(other)
                seen.append(taken)
        finally:
            await engine.dispose()

    monkeypatch.setattr(restore_module, "_restore_database", restore_and_try_a_backup)
    await restore_into_empty(
        target.settings, archive, without_secrets=False, clock=SettableClock(AT)
    )
    assert seen == [False], "a backup could start while the restore ran"
    engine = make_engine(target.settings.database())
    try:  # and released afterwards
        async with engine.connect() as after:
            assert await hold_backup_lock(after)
            await release_backup_lock(after)
    finally:
        await engine.dispose()
