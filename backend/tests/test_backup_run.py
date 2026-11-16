"""Scheduled backups (plan M9 decisions 7, 8 and 11): a run writes the archive, keeps
what the rule keeps and pushes it offsite with restic, which gets its own environment
and nothing else of the app's; the schedule fires at its cron term by the clock; the
worker's gauges come from `backup_run`."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.metrics import REGISTRY
from app.modules.backups.metrics import update_backup_metrics
from app.modules.backups.models import BackupRun, BackupState, BackupTrigger, OffsiteState
from app.ops.archive import sidecar_of
from app.ops.cli_run import run_backup
from app.ops.offsite import restic_env
from app.ops.schedule import next_due, run_schedule
from tests.real_db import RealDb
from tests.support.clock import SettableClock
from tests.support.fake_restic import calls, install_fake_restic

FIRST = datetime(2026, 12, 1, 2, 30, tzinfo=UTC)  # the first of a month: restic check too
REPOSITORY = "s3:https://s3.example.invalid/herd-backups"
RESTIC_PASSWORD = "restic-password-0123456789"


@pytest.fixture
def settings(tmp_path: Path, data_dir: Path) -> Settings:
    return Settings(
        database_url=get_settings().test_database_url,
        backup_dir=tmp_path / "backups",
        data_dir=data_dir,
        secret_key=SecretStr("s" * 40),
        backup_offsite_repository=REPOSITORY,
        backup_offsite_password=SecretStr(RESTIC_PASSWORD),
    )


@pytest.fixture
def restic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = install_fake_restic(tmp_path / "restic-bin")
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return directory


async def _runs(real_db: RealDb) -> list[BackupRun]:
    async with real_db.database.session_factory() as s:
        return list((await s.scalars(select(BackupRun).order_by(BackupRun.started_at))).all())


async def test_offsite_passes_only_its_own_environment(
    real_db: RealDb, settings: Settings, restic: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERD_DATABASE_PASSWORD", "database-password-of-the-app")
    monkeypatch.setenv("HERD_SECRET_KEY", "s" * 40)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret-example")
    monkeypatch.setenv("RESTIC_PASSWORD", "not-this-one")
    monkeypatch.setenv("RESTIC_COMPRESSION", "max")
    outcome = await run_backup(settings, SettableClock(FIRST), trigger=BackupTrigger.SCHEDULE)
    assert outcome.state == BackupState.OK and outcome.offsite == OffsiteState.OK
    assert outcome.archive is not None
    made = calls(restic)
    assert [c["argv"][0] for c in made] == ["cat", "init", "backup", "forget", "check"]
    backup = made[2]["argv"]
    assert str(outcome.archive) in backup and str(sidecar_of(outcome.archive)) in backup
    forget = made[3]["argv"]
    assert {"--prune", "--keep-daily=7", "--keep-weekly=4", "--keep-monthly=6"} <= set(forget)
    assert forget[forget.index("--group-by") + 1] == "host,tags"
    assert "--read-data-subset=5%" in made[4]["argv"]
    for call in made:
        env = call["env"]
        assert not any(name.startswith("HERD_") for name in env)
        assert env["RESTIC_REPOSITORY"] == REPOSITORY
        assert env["RESTIC_PASSWORD"] == RESTIC_PASSWORD
        assert env["AWS_ACCESS_KEY_ID"] == "AKIAEXAMPLE"
        assert env["RESTIC_COMPRESSION"] == "max"
        assert not any(RESTIC_PASSWORD in a or "database-password" in a for a in call["argv"])
    (run,) = await _runs(real_db)
    assert (run.trigger, run.state, run.offsite_state) == ("schedule", "ok", "ok")


async def test_offsite_failure_marks_offsite_failed_but_keeps_the_backup_ok(
    real_db: RealDb, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = install_fake_restic(tmp_path / "failing", fail=("backup",))
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    at = FIRST + timedelta(days=1)  # not the first: no check
    outcome = await run_backup(settings, SettableClock(at), trigger=BackupTrigger.SCHEDULE)
    assert outcome.state == BackupState.OK and outcome.offsite == OffsiteState.FAILED
    assert outcome.archive is not None and outcome.archive.exists()
    assert [c["argv"][0] for c in calls(directory)] == ["cat", "init", "backup"]
    (run,) = await _runs(real_db)
    assert (run.state, run.offsite_state) == ("ok", "failed")


async def test_without_a_repository_offsite_is_off_and_restic_never_runs(
    real_db: RealDb, settings: Settings, restic: Path
) -> None:
    plain = settings.model_copy(update={"backup_offsite_repository": ""})
    outcome = await run_backup(plain, SettableClock(FIRST), trigger=BackupTrigger.CLI)
    assert (outcome.state, outcome.offsite) == (BackupState.OK, OffsiteState.OFF)
    assert calls(restic) == []
    (run,) = await _runs(real_db)
    assert run.offsite_state == "off"


async def test_a_run_keeps_what_the_rule_keeps_and_a_failed_run_deletes_nothing(
    real_db: RealDb, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = settings.model_copy(
        update={
            "backup_offsite_repository": "",
            "backup_keep_daily": 2,
            "backup_keep_weekly": 0,
            "backup_keep_monthly": 0,
        }
    )
    clock = SettableClock(FIRST)
    for _ in range(4):
        assert (await run_backup(plain, clock, trigger=BackupTrigger.SCHEDULE)).state == "ok"
        clock.advance(timedelta(days=1))
    names = sorted(p.name for p in plain.backup_dir.glob("*.tar"))
    assert names == ["herd-20261203T023000Z-0.1.0.tar", "herd-20261204T023000Z-0.1.0.tar"]
    monkeypatch.setenv("PATH", "/nonexistent")  # pg_dump missing: the next run fails
    failed = await run_backup(plain, clock, trigger=BackupTrigger.SCHEDULE)
    assert failed.state == BackupState.FAILED
    assert sorted(p.name for p in plain.backup_dir.glob("*.tar")) == names


def test_restic_env_is_built_not_inherited() -> None:
    settings = Settings(
        backup_offsite_repository=REPOSITORY, backup_offsite_password=SecretStr(RESTIC_PASSWORD)
    )
    env = restic_env(
        settings,
        {
            "PATH": "/usr/bin",
            "HOME": "/tmp",
            "HERD_SECRET_KEY": "x" * 40,
            "PGPASSWORD": "pg",
            "B2_ACCOUNT_KEY": "b2",
            "AZURE_ACCOUNT_KEY": "az",
            "GOOGLE_APPLICATION_CREDENTIALS": "/secrets/gcs.json",
            "RESTIC_REPOSITORY": "other",
            "RESTIC_PASSWORD_FILE": "/elsewhere",
            "RESTIC_CACHE_DIR": "/cache",
        },
    )
    assert env == {
        "PATH": "/usr/bin",
        "HOME": "/tmp",
        "RESTIC_REPOSITORY": REPOSITORY,
        "RESTIC_PASSWORD": RESTIC_PASSWORD,
        "B2_ACCOUNT_KEY": "b2",
        "AZURE_ACCOUNT_KEY": "az",
        "GOOGLE_APPLICATION_CREDENTIALS": "/secrets/gcs.json",
        "RESTIC_CACHE_DIR": "/cache",
    }


def test_next_due_follows_the_cron_expression_in_utc() -> None:
    at = datetime(2026, 11, 15, 2, 29, 59, tzinfo=UTC)
    assert next_due("30 2 * * *", at) == datetime(2026, 11, 15, 2, 30, tzinfo=UTC)
    assert next_due("30 2 * * *", at + timedelta(seconds=1)) == datetime(
        2026, 11, 16, 2, 30, tzinfo=UTC
    )


async def test_schedule_fires_at_the_cron_term_without_sleeping(settings: Settings) -> None:
    clock = SettableClock(datetime(2026, 11, 15, 2, 0, tzinfo=UTC))
    fired: list[datetime] = []
    ran = asyncio.Event()

    async def run(settings: Settings, clock: SettableClock, *, trigger: BackupTrigger) -> None:
        assert trigger == BackupTrigger.SCHEDULE
        fired.append(clock.now())
        ran.set()

    stop = asyncio.Event()
    loop = asyncio.create_task(
        run_schedule(settings, clock, stop=stop, tick_seconds=0.001, run=run)  # type: ignore[arg-type]
    )
    try:
        for _ in range(20):  # some ticks before the term: nothing
            await asyncio.sleep(0.001)
        assert fired == []
        clock.set(datetime(2026, 11, 15, 2, 30, 5, tzinfo=UTC))
        await asyncio.wait_for(ran.wait(), 5)
        ran.clear()
        for _ in range(20):  # the same term never twice
            await asyncio.sleep(0.001)
        clock.set(datetime(2026, 11, 16, 2, 31, tzinfo=UTC))
        await asyncio.wait_for(ran.wait(), 5)
    finally:
        stop.set()
        await asyncio.wait_for(loop, 5)
    assert fired == [
        datetime(2026, 11, 15, 2, 30, 5, tzinfo=UTC),
        datetime(2026, 11, 16, 2, 31, tzinfo=UTC),
    ]


def _gauge(name: str) -> float:
    value = REGISTRY.get_sample_value(name)
    assert value is not None, name
    return value


async def test_backup_gauges_come_from_backup_run(real_db: RealDb) -> None:
    t0 = datetime(2026, 11, 14, 2, 30, tzinfo=UTC)
    async with real_db.database.session_factory() as session:
        rows = [
            BackupRun(
                org_id=real_db.org_id,
                trigger="schedule",
                state="ok",
                started_at=t0,
                finished_at=t0 + timedelta(minutes=2),
                bytes=1000,
                offsite_state="ok",
            ),
            BackupRun(
                org_id=real_db.org_id,
                trigger="schedule",
                state="ok",
                started_at=t0 + timedelta(days=1),
                finished_at=t0 + timedelta(days=1, minutes=3),
                bytes=2048,
                offsite_state="failed",
            ),
            BackupRun(
                org_id=real_db.org_id,
                trigger="cli",
                state="failed",
                started_at=t0 + timedelta(hours=5),
                finished_at=t0 + timedelta(hours=5, minutes=1),
                error_code="backup.io",
            ),
            BackupRun(
                org_id=real_db.org_id,
                trigger="cli",
                state="running",
                started_at=t0 + timedelta(days=2),
            ),
        ]
        session.add_all(rows)
        await session.commit()
    await update_backup_metrics(real_db.database, Settings(backup_alert_after_hours=30))
    ts = datetime.timestamp
    assert _gauge("herd_backup_last_success_timestamp_seconds") == ts(
        t0 + timedelta(days=1, minutes=3)
    )
    assert _gauge("herd_backup_last_failure_timestamp_seconds") == ts(
        t0 + timedelta(hours=5, minutes=1)
    )
    assert _gauge("herd_backup_last_bytes") == 2048
    assert _gauge("herd_backup_offsite_last_success_timestamp_seconds") == ts(
        t0 + timedelta(minutes=2)
    )
    assert _gauge("herd_backup_offsite_last_failure_timestamp_seconds") == ts(
        t0 + timedelta(days=1, minutes=3)
    )
    assert _gauge("herd_backup_alert_after_seconds") == 30 * 3600


async def test_backup_gauges_are_zero_before_the_first_backup(real_db: RealDb) -> None:
    await update_backup_metrics(real_db.database, Settings())
    assert _gauge("herd_backup_last_success_timestamp_seconds") == 0
    assert _gauge("herd_backup_last_bytes") == 0
    assert _gauge("herd_backup_alert_after_seconds") == 26 * 3600
