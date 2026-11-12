"""Application settings. Every value can be overridden with a HERD_* env var."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HERD_", env_file=".env", extra="ignore")

    environment: str = "development"  # development | test | production
    database_url: str = "postgresql+asyncpg://herd:herd@localhost:5433/herd"
    test_database_url: str = "postgresql+asyncpg://herd:herd@localhost:5433/herd_test"

    public_port: int = 8080
    internal_port: int = 9090
    internal_token: str = ""

    session_cookie_name: str = "herd_session"
    session_ttl_hours: int = 24 * 7
    cookie_secure: bool = False
    login_rate_limit_per_minute: int = 5

    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_org_name: str = "Meine Organisation"

    log_format: Literal["json", "text"] = "json"
    log_level: str = "INFO"
    role: Literal["api", "migrate", "all"] = "all"
    static_dir: Path | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
