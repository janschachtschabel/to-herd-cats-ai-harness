"""Review M9b final, finding F2-3: `HERD_DATABASE_SSLMODE=verify-ca` without
`HERD_DATABASE_SSLROOTCERT` still breaks every backup and restore (R18-2, half fixed).

The fix of R18-2 gives the PostgreSQL tools `PGSSLROOTCERT=system` for `verify-ca` and
`verify-full` alike. libpq takes `sslrootcert=system` only together with
`verify-full`: with `verify-ca` it refuses before it connects ("weak sslmode
"verify-ca" may not be used with sslrootcert=system"). The app itself (asyncpg,
`core/db_tls.py`) runs in that mode, against the system's CAs without the host name
check, so the installation works and `pg_dump`, `pg_restore` and `psql` do not."""

import subprocess

from app.core.config import Settings, get_settings
from app.ops.pgtools import child_env


def test_pg_dump_accepts_what_verify_ca_without_a_file_gives_it() -> None:
    """Whatever the test server's certificate is: libpq must not refuse the settings
    themselves before it looks at any certificate."""
    settings = Settings(database_url=get_settings().test_database_url, database_sslmode="verify-ca")
    env = child_env(settings) | {"HOME": "/nonexistent"}
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
