"""Settings that close ASVS gaps (plan M9 task 18): the write limits per person and
the optional virus scanner. A part of `Settings` (`config.py` inherits it);
`get_settings()` stays the one source."""

from pydantic import Field
from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    # Writes (messages, pages, tickets and the like) one person or one agent may make
    # per minute, and uploads (attachments, imports) apart; counted in PostgreSQL
    # across every node (J10, `core/write_limit.py`). Beyond: 429 `rate.limited`.
    write_rate_per_minute: int = Field(default=120, ge=1, le=100_000)
    upload_rate_per_minute: int = Field(default=30, ge=1, le=100_000)
