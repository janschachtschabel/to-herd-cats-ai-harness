"""How the app reaches PostgreSQL beyond the URL (plan M9 task 18): TLS (J12 a). A part
of `Settings` (`config.py` inherits it); `get_settings()` stays the one source.

HERD_DATABASE_SSLMODE takes libpq's modes and wins over an `ssl`/`sslmode` in the URL;
empty keeps the URL's (and asyncpg's default, `prefer`). HERD_DATABASE_SSLROOTCERT is
the CA file to verify the server against (`verify-ca`, `verify-full`); without it the
system's CAs. Both reach asyncpg (`core/db_tls.py`) and pg_dump/pg_restore
(`ops/pgtools.child_env`)."""

from pathlib import Path
from typing import Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")


class DatabaseSettings(BaseSettings):
    database_sslmode: str = ""
    database_sslrootcert: Path | None = None

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
        return self
