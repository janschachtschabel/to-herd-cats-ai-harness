"""What the backup report of M9 tasks 1 to 3 left (plan M9 task 8): a backup against a
database whose schema is behind or ahead of the code, or that cannot be reached, ends
with a code and no traceback; `backup run` by hand records `cli`, the cron job
`schedule`; a backup whose process died (killed by the job's time limit) does not stay
`running`: the next backup or the worker's due loop marks it `interrupted`, never one
whose process still holds the backup lock."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from app.core.config import Settings, get_settings
from app.core.db import make_engine
from app.core.listen import asyncpg_dsn
from app.core.migrations import alembic_config
from app.modules.backups.models import BackupRun, BackupState, BackupTrigger
from app.modules.backups.repository import BACKUP_LOCK
from app.ops.backup import create_backup
from app.ops.cli import run
from app.worker.due import DueLoop
from tests.factories_restore import Target
from tests.real_db import RealDb
from tests.support.clock import SettableClock

AT = datetime(2026, 11, 15, 2, 30, 7, tzinfo=UTC)


@pytest.fixture
def settings(tmp_path: Path, data_dir: Path) -> Settings:
    return Settings(
        database_url=get_settings().test_database_url,
        backup_dir=tmp_path / "backups",
        data_dir=data_dir,
        secret_key=SecretStr("g" * 40),
    )


async def _runs(real_db: RealDb) -> list[BackupRun]:
    async with real_db.database.session_factory() as s:
        return list((await s.scalars(select(BackupRun).order_by(BackupRun.started_at))).all())


async def _upgrade(target: Target, revision: str) -> None:
    engine = make_engine(target.settings.database())
    try:
        async with engine.begin() as conn:

            def go(sync_conn: object) -> None:
                config = alembic_config()
                config.attributes["connection"] = sync_conn
                command.upgrade(config, revision)

            await conn.run_sync(go)
    finally:
        await engine.dispose()


async def _execute(target: Target, sql: str) -> None:
    connection = await asyncpg.connect(asyncpg_dsn(make_url(target.settings.database_url)))
    try:
        await connection.execute(sql)
    finally:
        await connection.close()


def _previous_revision() -> str:
    script = ScriptDirectory.from_config(alembic_config())
    head = script.get_revision(script.get_current_head())
    assert head is not None and isinstance(head.down_revision, str)
    return head.down_revision


async def test_a_schema_behind_or_ahead_of_the_code_ends_with_a_code(
    target: Target, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = target.settings
    assert await run(["backup", "create"], settings, SettableClock(AT)) == 1
    assert capsys.readouterr().out.strip().splitlines()[-1] == "failed backup.no_schema"
    await _upgrade(target, _previous_revision())
    await _execute(target, "INSERT INTO organization (id, name) VALUES (gen_random_uuid(), 'O')")
    outcome = await create_backup(settings, trigger=BackupTrigger.CLI, clock=SettableClock(AT))
    assert (outcome.state, outcome.error_code, outcome.archive) == (
        BackupState.FAILED,
        "backup.schema_behind",
        None,
    )
    await _upgrade(target, "head")
    await _execute(target, "UPDATE alembic_version SET version_num = 'f00dfeedbeef'")
    assert await run(["backup", "run"], settings, SettableClock(AT)) == 1
    assert capsys.readouterr().out.strip().splitlines()[-1] == "failed backup.schema_ahead"
    assert not settings.backup_dir.exists() or not any(settings.backup_dir.iterdir())


async def test_an_unreachable_database_ends_with_a_code(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    url = make_url(settings.database_url).set(port=1)
    away = settings.model_copy(update={"database_url": url.render_as_string(False)})
    assert await run(["backup", "create"], away, SettableClock(AT)) == 1
    assert capsys.readouterr().out.strip().splitlines()[-1] == "failed backup.database_unavailable"


async def test_backup_run_records_cli_by_hand_and_schedule_from_the_cron_job(
    real_db: RealDb, settings: Settings
) -> None:
    assert await run(["backup", "run"], settings, SettableClock(AT)) == 0
    later = SettableClock(AT + timedelta(hours=1))
    assert await run(["backup", "run", "--scheduled"], settings, later) == 0
    assert [r.trigger for r in await _runs(real_db)] == [BackupTrigger.CLI, BackupTrigger.SCHEDULE]


async def _dead_run(real_db: RealDb, started: datetime) -> None:
    async with real_db.database.session_factory() as s:
        s.add(
            BackupRun(
                org_id=real_db.org_id,
                trigger=BackupTrigger.SCHEDULE,
                state=BackupState.RUNNING,
                started_at=started,
            )
        )
        await s.commit()


async def test_the_next_backup_marks_a_dead_one_interrupted(
    real_db: RealDb, settings: Settings
) -> None:
    await _dead_run(real_db, AT - timedelta(days=1))
    outcome = await create_backup(settings, trigger=BackupTrigger.CLI, clock=SettableClock(AT))
    assert outcome.state == BackupState.OK
    dead, made = await _runs(real_db)
    assert (dead.state, dead.finished_at) == (BackupState.INTERRUPTED, AT)
    assert made.state == BackupState.OK


async def test_the_due_loop_marks_a_dead_backup_and_leaves_a_live_one(
    real_db: RealDb, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    await _dead_run(real_db, AT - timedelta(hours=7))
    engine = make_engine(settings.database())
    try:
        async with engine.connect() as holder:  # a backup in progress holds the lock
            locked = await holder.scalar(
                text("SELECT pg_try_advisory_lock(hashtextextended(:k, 0))"), {"k": BACKUP_LOCK}
            )
            assert locked is True
            loop = DueLoop(real_db.database, clock=SettableClock(AT))
            await loop.cleanup_if_due()
            assert [r.state for r in await _runs(real_db)] == [BackupState.RUNNING]
            assert await run(["backup", "create"], settings, SettableClock(AT)) == 1
            assert (
                capsys.readouterr().out.strip().splitlines()[-1] == "failed backup.already_running"
            )
            await holder.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:k, 0))"), {"k": BACKUP_LOCK}
            )
    finally:
        await engine.dispose()
    await DueLoop(real_db.database, clock=SettableClock(AT)).cleanup_if_due()
    (dead,) = await _runs(real_db)
    assert (dead.state, dead.finished_at) == (BackupState.INTERRUPTED, AT)
