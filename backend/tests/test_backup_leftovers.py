"""What a backup killed midway leaves, and where the dump goes (module review M9a,
N2, N3, N9).

- A backup stopped by the job's time limit (SIGTERM, then SIGKILL), an OOM kill or a
  stopped container leaves its hidden `.herd-*.part` files on the backups volume. The
  next backup, holding the backup lock (so no other one is writing), removes them;
  nothing else in the directory.
- An `interrupted` backup counts as a failure (HerdBackupFailing).
- The scratch dump of a backup lies next to the archive on the backups volume, never in
  /tmp (a tmpfs in Compose, an emptyDir in the chart), and is gone afterwards; a
  restore streams the dump into pg_restore and needs no scratch file at all.
"""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.modules.backups.models import BackupRun, BackupState, BackupTrigger
from app.modules.backups.repository import BackupRunRepository
from app.ops.cli_run import run_backup
from app.ops.restore import restore_into_empty
from tests.factories_restore import Target, make_archive, source_settings
from tests.real_db import RealDb
from tests.support.clock import SettableClock

AT = datetime(2026, 11, 15, 2, 30, 7, tzinfo=UTC)
KILLED = (
    ".herd-20261114T023007Z-1.0.0.tar.part",
    ".herd-20261114T023007Z-1.0.0.manifest.json.part",
    ".herd-20261114T023007Z-1.0.0.db.dump.part",
)


@pytest.fixture
def settings(tmp_path: Path, data_dir: Path) -> Settings:
    return Settings(
        database_url=get_settings().test_database_url,
        backup_dir=tmp_path / "backups",
        data_dir=data_dir,
        secret_key=SecretStr("r" * 40),
    )


@pytest.fixture
def no_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """/tmp is gone: anything that puts a scratch file there fails."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "no-such-tmp"))


async def test_the_next_backup_removes_what_a_killed_one_left(
    real_db: RealDb, settings: Settings
) -> None:
    settings.backup_dir.mkdir(mode=0o700, parents=True)
    for name in KILLED:
        (settings.backup_dir / name).write_bytes(b"\0" * 4096)
    own = settings.backup_dir / ".operator-notes.part"  # not ours: stays
    own.write_text("kept")
    outcome = await run_backup(settings, SettableClock(AT), trigger=BackupTrigger.SCHEDULE)
    assert outcome.state == BackupState.OK
    left = sorted(p.name for p in settings.backup_dir.iterdir())
    assert outcome.archive is not None
    assert left == sorted(
        [
            ".operator-notes.part",
            outcome.archive.name,
            outcome.archive.name.removesuffix(".tar") + ".manifest.json",
        ]
    )


async def test_an_interrupted_backup_counts_as_a_failure(real_db: RealDb) -> None:
    async with real_db.database.session_factory() as s:
        s.add_all(
            [
                BackupRun(
                    org_id=real_db.org_id,
                    trigger=BackupTrigger.SCHEDULE,
                    state=BackupState.OK,
                    started_at=AT - timedelta(days=1),
                    finished_at=AT - timedelta(days=1),
                ),
                BackupRun(
                    org_id=real_db.org_id,
                    trigger=BackupTrigger.SCHEDULE,
                    state=BackupState.INTERRUPTED,
                    started_at=AT - timedelta(hours=7),
                    finished_at=AT,
                ),
            ]
        )
        await s.commit()
        figures = await BackupRunRepository(s).figures()
    assert figures.last_failed == AT


@pytest.mark.usefixtures("no_tmp")
async def test_a_backup_writes_its_dump_next_to_the_archive_not_to_tmp(
    real_db: RealDb, settings: Settings
) -> None:
    outcome = await run_backup(settings, SettableClock(AT), trigger=BackupTrigger.CLI)
    assert outcome.state == BackupState.OK, outcome.error_code
    assert not [p for p in settings.backup_dir.iterdir() if p.name.endswith(".part")]


async def test_a_restore_needs_no_scratch_file(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "no-such-tmp"))
    report = await restore_into_empty(
        target.settings, archive, without_secrets=False, clock=SettableClock(AT)
    )
    assert report.tables["organization"] == 1
