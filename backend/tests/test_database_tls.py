"""TLS to the database (plan M9 task 18, J12 a; ASVS 5.0 V12.3.1): HERD_DATABASE_SSLMODE
and HERD_DATABASE_SSLROOTCERT reach every connection of the app (asyncpg, through the
engine and the LISTEN connection) and PostgreSQL's own tools (`pg_dump`, `pg_restore`
through `PGSSLMODE`/`PGSSLROOTCERT`).

The test server may speak TLS (a local one with a snakeoil certificate) or not (CI's
image): the expectations follow what it does, and either way prove the setting reached
the client."""

import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings, get_settings
from app.core.db import make_engine
from app.core.listen import connect_listening
from app.ops.pgtools import child_env

# A CA certificate whose key signed nothing: no server certificate verifies against it.
UNRELATED_CA = Path(__file__).parent / "support" / "unrelated_ca.pem"
ENCRYPTED = text("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")


def _settings(mode: str, rootcert: Path | None = None) -> Settings:
    return Settings(
        database_url=get_settings().test_database_url,
        database_sslmode=mode,
        database_sslrootcert=rootcert,
    )


async def _encrypted(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            return bool(await conn.scalar(ENCRYPTED))
    finally:
        await engine.dispose()


def _pg_dump(settings: Settings) -> subprocess.CompletedProcess[str]:
    tool = shutil.which("pg_dump")
    assert tool is not None
    return subprocess.run(  # noqa: S603 (the tool from PATH, no shell)
        [tool, "--schema-only", "--table=alembic_version"],
        env=child_env(settings),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


async def test_sslmode_reaches_asyncpg_and_pg_dump(engine) -> None:
    async with engine.connect() as conn:
        server_tls = await conn.scalar(text("SHOW ssl")) == "on"

    plain = _settings("disable")
    assert await _encrypted(make_engine(settings=plain)) is False
    assert child_env(plain)["PGSSLMODE"] == "disable"
    assert _pg_dump(plain).returncode == 0

    required = _settings("require")
    assert child_env(required)["PGSSLMODE"] == "require"
    if server_tls:
        assert await _encrypted(make_engine(settings=required)) is True
        assert _pg_dump(required).returncode == 0
    else:
        with pytest.raises(Exception):  # noqa: B017 (asyncpg's "rejected SSL upgrade")
            await _encrypted(make_engine(settings=required))
        assert _pg_dump(required).returncode != 0

    # verify-full against a CA that signed nothing: no connection, whether the server
    # speaks TLS (the certificate does not verify) or not (TLS is required).
    strict = _settings("verify-full", UNRELATED_CA)
    env = child_env(strict)
    assert env["PGSSLMODE"] == "verify-full" and env["PGSSLROOTCERT"] == str(UNRELATED_CA)
    with pytest.raises(Exception):  # noqa: B017
        await _encrypted(make_engine(settings=strict))
    assert _pg_dump(strict).returncode != 0
    with pytest.raises(Exception):  # noqa: B017 (the LISTEN connection, too)
        await connect_listening(strict.database(), strict)


def test_the_setting_wins_over_the_urls_sslmode() -> None:
    settings = Settings(
        database_url=get_settings().test_database_url + "?ssl=disable",
        database_sslmode="verify-full",
        database_sslrootcert=UNRELATED_CA,
    )
    assert child_env(settings)["PGSSLMODE"] == "verify-full"


def test_no_sslmode_keeps_the_urls_own() -> None:
    settings = Settings(database_url=get_settings().test_database_url + "?ssl=require")
    assert child_env(settings)["PGSSLMODE"] == "require"
    assert "PGSSLROOTCERT" not in child_env(settings)


def test_a_root_certificate_must_be_readable(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="HERD_DATABASE_SSLROOTCERT"):
        _settings("verify-full", tmp_path / "missing.pem")
    with pytest.raises(ValueError, match="HERD_DATABASE_SSLMODE"):
        Settings(database_sslmode="sometimes")  # type: ignore[arg-type]


def test_an_empty_root_certificate_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERD_DATABASE_SSLROOTCERT", "")
    assert Settings().database_sslrootcert is None
