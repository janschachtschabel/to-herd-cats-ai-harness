"""Review of M9b Task 18 (R18-2): `HERD_DATABASE_SSLMODE=verify-full`
without `HERD_DATABASE_SSLROOTCERT` must mean the same for the app and for the
PostgreSQL tools: the system's CAs, as the README, `config_database.py` and the chart's
`database.caSecret` ("Empty: the image's system CAs") say.

asyncpg gets `ssl.create_default_context()` (the system's CAs). pg_dump, pg_restore
and psql get `PGSSLMODE` alone, and libpq then looks for `~/.postgresql/root.crt`
only; it takes the system's CAs just with `sslrootcert=system` (PostgreSQL 16 and
later; the image ships 17). So with a database whose certificate a public CA signed,
the app runs and every backup and restore fails."""

import subprocess

from app.core.config import Settings, get_settings
from app.ops.pgtools import child_env


def _settings(mode: str) -> Settings:
    return Settings(database_url=get_settings().test_database_url, database_sslmode=mode)


def test_the_tools_verify_against_the_systems_cas_like_the_app() -> None:
    """Only for verify-full: libpq refuses `sslrootcert=system` with verify-ca, which
    therefore needs HERD_DATABASE_SSLROOTCERT (review M9b final, F2-3)."""
    env = child_env(_settings("verify-full"))
    assert env["PGSSLMODE"] == "verify-full"
    assert env.get("PGSSLROOTCERT") == "system"


def test_pg_dump_does_not_ask_for_a_root_crt_in_the_home_directory() -> None:
    """Whatever the test server's certificate is: libpq must not stop at a missing
    `~/.postgresql/root.crt` before it looks at any certificate."""
    env = child_env(_settings("verify-full")) | {"HOME": "/nonexistent"}
    done = subprocess.run(  # noqa: S603
        [
            "pg_dump",
            "--schema-only",
            "--no-password",
            "--file=/dev/null",  # noqa: S607
            f"--dbname={env.get('PGDATABASE', '')}",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "root.crt" not in done.stderr, done.stderr
