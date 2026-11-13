"""Application settings. Every value can be overridden with a HERD_* env var."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, PrivateAttr, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

from app.core.password_rule import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

INTERNAL_TOKEN_MIN_LENGTH = 32
SECRET_KEY_MIN_LENGTH = 32
_REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/app/core/config.py -> repo


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
    # Guards /internal/* (header X-Herd-Internal-Token); unset, /internal/* answers 503.
    # Shared with the collab process. At least 32 characters (`openssl rand -hex 32`).
    internal_token: SecretStr | None = None
    # The address browsers use (scheme://host[:port]); WebSocket Origins must match it.
    # Unset, an Origin must match the host the request came to.
    public_url: str | None = None
    # Live editing: where the API relays /collab to (the collab process), the port the
    # collab process listens on, how it reaches the internal API (default: this
    # process's internal port), and its script (`node <collab_script>`).
    collab_url: str = "ws://127.0.0.1:1234"
    collab_port: int = 1234
    collab_api_url: str | None = None
    collab_script: Path = _REPO_ROOT / "collab" / "server.mjs"

    session_cookie_name: str = "herd_session"
    session_ttl_hours: int = 24 * 7
    cookie_secure: bool = False
    # Reverse proxies whose X-Forwarded-For/-Proto the public port believes (comma
    # separated IPs or networks, "*" for any); the client IP and scheme come from them.
    forwarded_allow_ips: str = "127.0.0.1"
    # Failed logins per client address and email, and all logins per client address.
    login_rate_limit_per_minute: int = 5
    login_ip_rate_limit_per_minute: int = 30
    # argon2 computations at a time per process (each ~64 MiB, off the event loop).
    password_hash_concurrency: int = Field(default=2, ge=1)
    # Requests that may wait for one of those slots; more are answered 429 at once.
    password_hash_queue: int = Field(default=16, ge=0)
    # Largest request body accepted (bytes); larger ones are answered 413.
    max_body_bytes: int = Field(default=1024 * 1024, ge=1)
    # Most lines (both versions together) a page diff compares; more is answered 422.
    diff_max_lines: int = Field(default=20_000, ge=1)
    # Where files live (attachments); a volume shared by all API replicas.
    data_dir: Path = Path("/data")
    # Largest attachment (bytes); its upload route takes bodies up to this size.
    attachment_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1)
    # Largest Markdown ZIP to import (bytes, packed); its route takes bodies this large.
    import_max_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
    # Longest wait (seconds) for the next part of an upload's or import's body: 408 after.
    body_read_timeout_seconds: float = Field(default=30.0, gt=0)
    # Longest time (seconds) a whole upload or import body may take: 408 after.
    body_total_timeout_seconds: float = Field(default=900.0, gt=0)

    # Live delivery: when the oldest event waiting in an API process's hub is older
    # than this (seconds), the hub drops what waits and tells its streams to reload.
    live_max_lag_seconds: float = Field(default=5.0, gt=0)

    # The worker: longest time (seconds) one outbox handler may take for one event
    # (asyncio and the transaction's lock_timeout/statement_timeout); a timeout is a
    # failed attempt. A worker without progress for 4 times this is not ready.
    worker_handler_timeout_seconds: float = Field(default=30.0, gt=0)

    # AI connections (M5). The key for `enc:` secret references (API keys), at least 32
    # characters (`openssl rand -hex 32`); unset, only `env:HERD_AI_*` references are
    # possible. During a rotation the old key goes to HERD_SECRET_KEY_PREVIOUS: it still
    # decrypts, never encrypts (`scripts/rotate_secrets.py`, docs/KI.md).
    secret_key: SecretStr | None = None
    secret_key_previous: SecretStr | None = None
    # Longest wait (seconds) for a provider when testing a connection or listing models.
    ai_check_timeout_seconds: float = Field(default=20.0, gt=0)

    bootstrap_admin_email: str = ""
    bootstrap_admin_password: SecretStr = SecretStr("")
    bootstrap_org_name: str = "Meine Organisation"

    log_format: Literal["json", "text"] = "json"
    log_level: str = "INFO"
    role: Literal["api", "migrate", "all", "collab", "worker"] = "all"
    static_dir: Path | None = None

    _database_password: SecretStr | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _bootstrap_password_follows_the_rule(self) -> Self:
        length = len(self.bootstrap_admin_password.get_secret_value())
        if length and not PASSWORD_MIN_LENGTH <= length <= PASSWORD_MAX_LENGTH:
            raise ValueError(
                "HERD_BOOTSTRAP_ADMIN_PASSWORD must be "
                f"{PASSWORD_MIN_LENGTH} to {PASSWORD_MAX_LENGTH} characters long"
            )
        return self

    @model_validator(mode="after")
    def _internal_token_is_long_enough(self) -> Self:
        if self.internal_token is not None:
            length = len(self.internal_token.get_secret_value())
            if length == 0:
                self.internal_token = None
            elif length < INTERNAL_TOKEN_MIN_LENGTH:
                raise ValueError(
                    f"HERD_INTERNAL_TOKEN must be at least {INTERNAL_TOKEN_MIN_LENGTH} characters"
                )
        return self

    @model_validator(mode="after")
    def _secret_keys_are_long_enough(self) -> Self:
        for name in ("secret_key", "secret_key_previous"):
            value: SecretStr | None = getattr(self, name)
            if value is not None and not value.get_secret_value():
                setattr(self, name, None)  # compose: `${HERD_SECRET_KEY:-}`
            elif value is not None and len(value.get_secret_value()) < SECRET_KEY_MIN_LENGTH:
                raise ValueError(
                    f"HERD_{name.upper()} must be at least {SECRET_KEY_MIN_LENGTH} characters"
                )
        return self

    @model_validator(mode="after")
    def _public_url_is_an_origin(self) -> Self:
        if self.public_url == "":
            self.public_url = None  # compose: `${HERD_PUBLIC_URL:-}`
        if self.public_url is not None:
            url = urlsplit(self.public_url)
            if url.scheme not in ("http", "https") or not url.netloc:
                raise ValueError("HERD_PUBLIC_URL must be an http(s) URL like https://wiki.example")
        return self

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
