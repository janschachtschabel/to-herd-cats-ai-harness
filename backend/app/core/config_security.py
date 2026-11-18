"""Settings that close ASVS gaps (plan M9 task 18): the write limits per person and
the optional virus scanner. A part of `Settings` (`config.py` inherits it);
`get_settings()` stays the one source."""

import re
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

_HOST_PORT = re.compile(r"[A-Za-z0-9.-]+:(\d{1,5})|\[[0-9A-Fa-f:.]+\]:(\d{1,5})")


class SecuritySettings(BaseSettings):
    # Writes (messages, pages, tickets and the like) one person or one agent may make
    # per minute, and uploads (attachments, imports) apart; counted in PostgreSQL
    # across every node (J10, `core/write_limit.py`). Beyond: 429 `rate.limited`.
    write_rate_per_minute: int = Field(default=120, ge=1, le=100_000)
    upload_rate_per_minute: int = Field(default=30, ge=1, le=100_000)
    # The optional virus scanner (J11, `core/virus_scan.py`): clamd's TCP address as
    # `host:port` (its port is usually 3310). Empty: no scan. Set, attachments and
    # imports are scanned before they are stored and refused when the scan fails.
    clamav_address: str = ""

    @model_validator(mode="after")
    def _clamav_address_is_host_and_port(self) -> Self:
        if self.clamav_address:
            match = _HOST_PORT.fullmatch(self.clamav_address)
            port = int(next(p for p in match.groups() if p)) if match else 0
            if not 1 <= port <= 65535:
                raise ValueError("HERD_CLAMAV_ADDRESS must be host:port, e.g. clamav:3310")
        return self
