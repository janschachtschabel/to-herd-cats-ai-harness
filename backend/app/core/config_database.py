"""How the app reaches PostgreSQL beyond the URL (plan M9 task 18): TLS (J12 a) and
separate roles (J14, `core/db_roles.py`). A part of `Settings` (`config.py` inherits
it); `get_settings()` stays the one source.

HERD_MIGRATE_DATABASE_URL (without its password; that is HERD_MIGRATE_DATABASE_PASSWORD
or its _FILE) is the schema owner's, for migrations, backups and restores; empty: they
use HERD_DATABASE_URL. HERD_DATABASE_RUNTIME_ROLE names the role of HERD_DATABASE_URL
that migrations give data rights only.

HERD_DATABASE_SSLMODE takes libpq's modes and wins over an `ssl`/`sslmode` in the URL;
empty keeps the URL's (and asyncpg's default, `prefer`). HERD_DATABASE_SSLROOTCERT is
the CA file to verify the server against (`verify-ca`, `verify-full`); `verify-full`
without it checks the system's CAs, `verify-ca` without it is refused (libpq's tools
take the system's CAs only with `verify-full`). Both reach asyncpg (`core/db_tls.py`)
and pg_dump/pg_restore (`ops/pgtools.child_env`)."""

import re
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine import URL, make_url

SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
# A plain, unquoted PostgreSQL role name (lower case: what the URL's user becomes).
_ROLE = re.compile(r"[a-z_][a-z0-9_]{0,62}")


class DatabaseSettings(BaseSettings):
    database_sslmode: str = ""
    database_sslrootcert: Path | None = None
    migrate_database_url: str = Field(default="", repr=False)
    migrate_database_password: SecretStr | None = None
    database_runtime_role: str = ""

    @field_validator("database_sslrootcert", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        return None if value == "" else value  # compose passes an unset one as ""

    @model_validator(mode="after")
    def _tls_is_usable(self) -> Self:
        if self.database_sslmode and self.database_sslmode not in SSL_MODES:
            raise ValueError(f"HERD_DATABASE_SSLMODE must be one of {', '.join(SSL_MODES)}")
        cert = self.database_sslrootcert
        if cert is not None and not cert.is_file():
            raise ValueError("HERD_DATABASE_SSLROOTCERT cannot be read: no such file")
        # libpq's tools take the system's CAs (`sslrootcert=system`) only with
        # verify-full; with verify-ca every backup and restore would fail (F2-3).
        if self.database_sslmode == "verify-ca" and cert is None:
            raise ValueError(
                "HERD_DATABASE_SSLMODE=verify-ca needs HERD_DATABASE_SSLROOTCERT (the CA "
                "file); without one use verify-full, which checks the system's CAs"
            )
        return self

    @model_validator(mode="after")
    def _runtime_role_is_a_name(self) -> Self:
        role = self.database_runtime_role
        if role and not _ROLE.fullmatch(role):
            raise ValueError("HERD_DATABASE_RUNTIME_ROLE must be a plain role name (a-z, 0-9, _)")
        # A migration role without a runtime role to give rights to would leave the
        # app's own role unable to read the tables the migrations make.
        if self.migrate_database_url and not role:
            raise ValueError("HERD_MIGRATE_DATABASE_URL needs HERD_DATABASE_RUNTIME_ROLE")
        return self

    def migrate_database_url_with_password(self) -> URL | None:
        """The migration role's URL with its password, or None (one role)."""
        if not self.migrate_database_url:
            return None
        url = make_url(self.migrate_database_url)
        if self.migrate_database_password is not None:
            url = url.set(password=self.migrate_database_password.get_secret_value())
        return url
