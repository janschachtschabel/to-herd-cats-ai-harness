"""Review M9b final, finding F2-3: `HERD_DATABASE_SSLMODE=verify-ca` without
`HERD_DATABASE_SSLROOTCERT` broke every backup and restore (R18-2, half fixed).

libpq takes `sslrootcert=system` only together with `verify-full`: with `verify-ca` it
refuses before it connects ("weak sslmode "verify-ca" may not be used with
sslrootcert=system"). The app itself (asyncpg, `core/db_tls.py`) ran in that mode, so
the installation worked and `pg_dump`, `pg_restore` and `psql` did not.

Ruling: `verify-ca` without a CA file is refused at start with a settings error that
names `HERD_DATABASE_SSLROOTCERT`; the tools get `PGSSLROOTCERT=system` only for
`verify-full`."""

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.ops.pgtools import child_env

UNRELATED_CA = Path(__file__).parent / "support" / "unrelated_ca.pem"


def test_verify_ca_without_a_ca_file_is_refused_at_start() -> None:
    with pytest.raises(ValidationError) as refused:
        Settings(database_url=get_settings().test_database_url, database_sslmode="verify-ca")
    assert "HERD_DATABASE_SSLROOTCERT" in str(refused.value)


def test_pg_dump_accepts_what_verify_ca_with_a_file_gives_it() -> None:
    """Whatever the test server's certificate is: libpq must not refuse the settings
    themselves before it looks at any certificate."""
    settings = Settings(
        database_url=get_settings().test_database_url,
        database_sslmode="verify-ca",
        database_sslrootcert=UNRELATED_CA,
    )
    env = child_env(settings) | {"HOME": "/nonexistent"}
    assert env["PGSSLROOTCERT"] == str(UNRELATED_CA)
    done = subprocess.run(  # noqa: S603
        [
            "pg_dump",  # noqa: S607
            "--schema-only",
            "--no-password",
            "--file=/dev/null",
            f"--dbname={env.get('PGDATABASE', '')}",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "weak sslmode" not in done.stderr, done.stderr
    assert "root.crt" not in done.stderr, done.stderr
