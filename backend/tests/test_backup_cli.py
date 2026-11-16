"""`python -m app.ops backup create|verify|list` (plan M9 task 1): the exit status says
whether it worked, the output names the archive or the problem codes, and `list`
shows the recorded runs, newest first."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.ops.cli import run
from app.version import app_version
from tests.real_db import RealDb
from tests.support.clock import SettableClock

AT = datetime(2026, 11, 15, 2, 30, 7, tzinfo=UTC)


@pytest.fixture
def settings(tmp_path: Path, data_dir: Path) -> Settings:
    return Settings(
        database_url=get_settings().test_database_url,
        backup_dir=tmp_path / "backups",
        data_dir=data_dir,
        secret_key=SecretStr("c" * 40),
    )


def _size(path: Path) -> int:
    return path.stat().st_size


def _flip_a_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[len(data) // 3] ^= 0xFF
    path.write_bytes(bytes(data))


async def test_create_verify_and_list(
    real_db: RealDb, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    clock = SettableClock(AT)
    assert await run(["backup", "create"], settings, clock) == 0
    archive = Path(capsys.readouterr().out.strip().splitlines()[-1])
    assert archive == settings.backup_dir / f"herd-20261115T023007Z-{app_version()}.tar"

    assert await run(["backup", "verify", str(archive)], settings, clock) == 0
    assert capsys.readouterr().out.strip() == "ok"

    clock.set(datetime(2026, 11, 16, 2, 30, 7, tzinfo=UTC))
    other = settings.model_copy(update={"backup_dir": settings.backup_dir / "elsewhere"})
    assert await run(["backup", "create", "--dir", str(other.backup_dir)], settings, clock) == 0
    second = Path(capsys.readouterr().out.strip().splitlines()[-1])
    assert second.parent == other.backup_dir

    assert await run(["backup", "list", "--limit", "5"], settings, clock) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].split() == [
        "started",
        "finished",
        "trigger",
        "state",
        "bytes",
        "sha256",
        "archive",
        "error",
        "offsite",
    ]
    newest, oldest = (line.split() for line in lines[1:])
    assert newest[0] == "2026-11-16T02:30:07Z" and newest[6] == second.name
    assert oldest[2:4] == ["cli", "ok"] and oldest[4] == str(_size(archive))
    assert oldest[7:] == ["-", "off"] and len(oldest[5]) == 12

    _flip_a_byte(archive)
    assert await run(["backup", "verify", str(archive)], settings, clock) == 1
    assert capsys.readouterr().out.split() == ["archive.checksum", "archive.member_checksum"]


async def test_a_failed_backup_says_its_code(
    real_db: RealDb,
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    assert await run(["backup", "create"], settings, SettableClock(AT)) == 1
    # (the warning's log line comes first: logging goes to stdout here)
    assert capsys.readouterr().out.strip().splitlines()[-1] == "failed backup.tool_missing"
    assert await run(["backup", "list"], settings, SettableClock(AT)) == 0
    (_, row) = capsys.readouterr().out.strip().splitlines()
    assert row.split()[2:] == ["cli", "failed", "-", "-", "-", "backup.tool_missing", "off"]


async def test_backup_run_from_the_command_line(
    real_db: RealDb, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await run(["backup", "run"], settings, SettableClock(AT)) == 0
    last = capsys.readouterr().out.strip().splitlines()[-1]
    name = f"herd-20261115T023007Z-{app_version()}.tar"
    assert last == f"{settings.backup_dir / name} offsite=off"
