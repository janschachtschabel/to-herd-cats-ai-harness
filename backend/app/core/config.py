"""Application settings. Every value can be overridden with a HERD_* env var."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, PrivateAttr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

from app.core.config_ops import OpsSettings
from app.core.password_rule import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

INTERNAL_TOKEN_MIN_LENGTH = 32
SECRET_KEY_MIN_LENGTH = 32
_REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/app/core/config.py -> repo


class Settings(OpsSettings, BaseSettings):
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
    # An explicit proxy for calls to AI providers (`http://[user:password@]host:port`),
    # set by the operator where providers are reachable only through one (ruling M5 (a));
    # `local` connections never use it. HTTPS_PROXY and the like stay ignored.
    ai_egress_proxy: SecretStr | None = None
    # Agent runs (M5 task 6): how many runs one worker process works on at once; the
    # lease (seconds) a running run holds, renewed while it works (a crashed worker's
    # run is taken up again after it).
    run_concurrency: int = Field(default=4, ge=1, le=64)
    run_lease_seconds: float = Field(default=30.0, ge=3)
    # Personal agents one person may have at most (plan M6 decision 13).
    ai_personal_agents_max: int = Field(default=5, ge=0, le=100)
    # Automations one person may own at most, not counting done or deleted ones (plan
    # M7 decision 12).
    ai_automations_max: int = Field(default=20, ge=0, le=1000)
    # How long a run waits for a release or an answer (hours, plan M6 task 7) before it
    # ends (`approval_expired`, `waiting_timeout`).
    ai_approval_hours: float = Field(default=72.0, gt=0, le=720)
    # Calls one access token may make to `/mcp` per minute, counted in Postgres across
    # every API node (plan M8 decision 6).
    mcp_rate_per_minute: int = Field(default=120, ge=1, le=10_000)
    # External MCP servers inside the company network (an in-house GitLab): host names
    # or private networks (CIDR), comma separated, that the egress guard lets their
    # calls reach (`core/egress_allowance.py`); empty: public addresses only.
    mcp_allowed_hosts: str = ""
    # The operator's own catalogue entries (plan M8 task 9): a directory of YAML files
    # added to the shipped ones; a broken file is reported and skipped, never fatal.
    mcp_catalog_dir: Path | None = None
    # Calls one agent run may send to external MCP servers at most (plan M8 task 13);
    # the next is refused as a result, nothing is sent. They cost no model tokens, so no
    # budget counts them: this cap is what bounds them.
    mcp_max_calls_per_run: int = Field(default=20, ge=1, le=500)

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
    def _empty_egress_proxy_is_none(self) -> Self:
        if self.ai_egress_proxy is not None and not self.ai_egress_proxy.get_secret_value():
            self.ai_egress_proxy = None  # compose: `${HERD_AI_EGRESS_PROXY:-}`
        return self

    @field_validator("mcp_catalog_dir", mode="before")
    @classmethod
    def _empty_catalog_dir_is_none(cls, value: object) -> object:
        return None if value == "" else value  # compose: `${HERD_MCP_CATALOG_DIR:-}`

    @model_validator(mode="after")
    def _mcp_allowed_hosts_parse(self) -> Self:
        from app.core.egress_allowance import parse_allowance  # noqa: PLC0415 (light start)

        parse_allowance(self.mcp_allowed_hosts)
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
