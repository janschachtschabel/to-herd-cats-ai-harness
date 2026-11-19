"""The backup lock's holder (module review M9a re-check, P2).

A backup holds the session-level advisory lock `herd.backup` on a connection of its
own while it runs; since N2 the lock also guards removing `.herd-*.part` files. So:

- the holder never idles in a transaction (a server's
  `idle_in_transaction_session_timeout` would end the session, and the lock with it,
  while the backup goes on): it commits right after taking the lock, as
  `schema_lock.py` does;
- a holder whose connection is gone by the end (the session lock went with it) does
  not turn a finished backup into an exception: the release logs a code, and
  retention runs as after any good backup.
"""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings, get_settings
from app.core.db import make_engine
from app.modules.backups.models import BackupState, BackupTrigger
from app.modules.backups.repository import hold_backup_lock, release_backup_lock
from app.ops import backup
from app.ops.cli_run import run_backup
from tests.real_db import RealDb
from tests.support.clock import SettableClock

AT = datetime(2026, 11, 15, 2, 30, 7, tzinfo=UTC)
OLD = "herd-20261115T013007Z-1.0.0"  # a good older archive that retention removes


async def test_the_backup_lock_holder_is_idle_right_after_taking_the_lock() -> None:
    engine = make_engine(get_settings().test_database_url)
    try:
        async with engine.connect() as holder, engine.connect() as other:
            pid = await holder.scalar(text("SELECT pg_backend_pid()"))
            await holder.commit()
            assert await hold_backup_lock(holder)
            state = await other.scalar(
                text("SELECT state FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}
            )
            await release_backup_lock(holder)
    finally:
        await engine.dispose()
    assert state == "idle", state


async def test_the_backup_lock_survives_an_idle_in_transaction_timeout() -> None:
    # As on a server whose policy ends sessions idle in a transaction for 300 ms.
    strict = make_engine(
        get_settings().test_database_url,
        connect_args={"server_settings": {"idle_in_transaction_session_timeout": "300"}},
    )
    engine = make_engine(get_settings().test_database_url)
    taken: bool | None = None
    try:
        async with strict.connect() as holder:
            assert await hold_backup_lock(holder)
            await asyncio.sleep(1.0)  # the backup's pg_dump runs on other connections
            async with engine.connect() as second:
                taken = await hold_backup_lock(second)
                if taken:
                    await release_backup_lock(second)
            await release_backup_lock(holder)
    finally:
        await strict.dispose()
        await engine.dispose()
    assert taken is False, "a second backup took the lock while the first one was still running"


@pytest.fixture
def settings(tmp_path: Path, data_dir: Path) -> Settings:
    return Settings(
        database_url=get_settings().test_database_url,
        backup_dir=tmp_path / "backups",
        data_dir=data_dir,
        secret_key=SecretStr("r" * 40),
        backup_keep_daily=1,
        backup_keep_weekly=0,
        backup_keep_monthly=0,
    )


async def test_a_lost_lock_connection_does_not_fail_a_finished_backup(
    real_db: RealDb,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    write = backup._write

    async def write_then_lose_the_holder(
        s: Settings, engine: AsyncEngine, path: Path, at: datetime
    ) -> str:
        sha = await write(s, engine, path, at)
        async with engine.connect() as conn:  # the server ends the holder's session
            ended = await conn.scalar(
                text(
                    "SELECT count(pg_terminate_backend(pid)) FROM pg_locks"
                    " WHERE locktype = 'advisory' AND granted AND pid <> pg_backend_pid()"
                    " AND database = (SELECT oid FROM pg_database"
                    " WHERE datname = current_database())"
                )
            )
        assert ended == 1
        return sha

    first = await run_backup(settings, SettableClock(AT), trigger=BackupTrigger.CLI)
    assert first.archive is not None
    old = first.archive.with_name(f"{OLD}.tar")
    first.archive.rename(old)
    backup.sidecar_of(first.archive).rename(backup.sidecar_of(old))
    monkeypatch.setattr(backup, "_write", write_then_lose_the_holder)

    with caplog.at_level(logging.WARNING, logger="app.ops.backup"):
        outcome = await run_backup(
            settings, SettableClock(AT.replace(hour=3)), trigger=BackupTrigger.CLI
        )

    assert outcome.state == BackupState.OK, outcome.error_code
    assert "backup.lock_release_failed" in [r.getMessage() for r in caplog.records]
    assert not old.exists(), "retention did not run"
