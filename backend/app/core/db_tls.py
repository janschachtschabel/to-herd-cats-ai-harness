"""TLS of the app's own database connections (plan M9 task 18, J12 a; ASVS 5.0
V12.3.1): HERD_DATABASE_SSLMODE and HERD_DATABASE_SSLROOTCERT as asyncpg's `ssl`
argument, with libpq's meaning, for the engine (`db.make_engine`) and the LISTEN
connection (`listen.connect_listening`). pg_dump and pg_restore get the same through
`PGSSLMODE`/`PGSSLROOTCERT` (`ops/pgtools.child_env`)."""

import ssl
from typing import Any

from app.core.config import Settings


def connect_args(settings: Settings) -> dict[str, Any]:
    """asyncpg's `ssl` for the configured mode; nothing when none is configured (the
    URL's own `ssl`/`sslmode`, or asyncpg's default, stays)."""
    mode = settings.database_sslmode
    if not mode:
        return {}
    if mode in ("disable", "allow", "prefer"):
        return {"ssl": mode}
    cafile = str(settings.database_sslrootcert) if settings.database_sslrootcert else None
    context = ssl.create_default_context(cafile=cafile)
    if mode == "verify-full":
        return {"ssl": context}
    context.check_hostname = False
    # libpq: `require` with a root certificate verifies the chain like `verify-ca`.
    if mode == "require" and cafile is None:
        context.verify_mode = ssl.CERT_NONE
    return {"ssl": context}
