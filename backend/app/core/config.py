"""Application settings. Every value can be overridden with a HERD_* env var."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, PrivateAttr, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    # hide_input_in_errors: a start-up error must not echo secrets from the environment.
    model_config = SettingsConfigDict(
        env_prefix="HERD_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    environment: str = "development"  # development | test | production
    # The password belongs in HERD_DATABASE_PASSWORD or HERD_DATABASE_PASSWORD_FILE
    # (merged in by `database()`); a URL with a password still works (tests, local dev).
    database_url: str = Field(
        default="postgresql+asyncpg://herd:herd@localhost:5433/herd", repr=False
    )
    database_password: SecretStr | None = None
    database_password_file: Path | None = None
    test_database_url: str = Field(
        default="postgresql+asyncpg://herd:herd@localhost:5433/herd_test", repr=False
    )

    public_port: int = 8080
    internal_port: int = 9090
    internal_token: SecretStr = SecretStr("")

    session_cookie_name: str = "herd_session"
    session_ttl_hours: int = 24 * 7
    cookie_secure: bool = False
    # Reverse proxies whose X-Forwarded-For/-Proto the public port believes (comma
    # separated IPs or networks, "*" for any); the client IP and scheme come from them.
    forwarded_allow_ips: str = "127.0.0.1"
    login_rate_limit_per_minute: int = 5

    bootstrap_admin_email: str = ""
    bootstrap_admin_password: SecretStr = SecretStr("")
    bootstrap_org_name: str = "Meine Organisation"

    log_format: Literal["json", "text"] = "json"
    log_level: str = "INFO"
    role: Literal["api", "migrate", "all"] = "all"
    static_dir: Path | None = None

    _database_password: SecretStr | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _resolve_database_password(self) -> Self:
        if self.database_password is not None and self.database_password_file is not None:
            raise ValueError("set HERD_DATABASE_PASSWORD or HERD_DATABASE_PASSWORD_FILE, not both")
        if self.database_password_file is not None:
            try:
                content = self.database_password_file.read_text(encoding="utf-8")
            except OSError as exc:
                raise ValueError(
                    f"HERD_DATABASE_PASSWORD_FILE cannot be read: {exc.strerror}"
                ) from None
            content = content.rstrip("\r\n")  # mounted secrets often end with a newline
            if not content:
                raise ValueError("HERD_DATABASE_PASSWORD_FILE is empty")
            self._database_password = SecretStr(content)
        else:
            self._database_password = self.database_password
        return self

    def database(self) -> URL:
        """The connection URL with the separate password merged in (escaped when the
        URL is rendered). `str()` and `repr()` of the URL mask the password."""
        url = make_url(self.database_url)
        if self._database_password is not None:
            url = url.set(password=self._database_password.get_secret_value())
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
