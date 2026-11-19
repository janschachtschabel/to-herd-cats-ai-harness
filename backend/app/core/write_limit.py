"""The write limit per person and minute (ASVS 5.0 V2.4.1, plan M9 task 18, J10), on the
PostgreSQL rate limiter (`ratelimit.py`), so it holds across every node.

- Two areas, each its own count: `write` (messages, pages, tickets, reactions and the
  like; `HERD_WRITE_RATE_PER_MINUTE`, 120) and `upload` (attachments, imports;
  `HERD_UPLOAD_RATE_PER_MINUTE`, 30).
- Counted per writer: a person by her id, an agent by its own (`agent:<id>`), so an
  agent counts like a person and never uses up the count of whoever asked it.
- A request is counted before it does anything (`admit_now`, committed at once, so no
  lock is held while it writes); a tool of an agent run or of `/mcp` inside the step's
  transaction (`admit_within`), so a step that rolls back has not counted.
- Beyond the limit: 429 `rate.limited` with `Retry-After` (seconds until the oldest
  write of the window leaves it); `herd_rate_limited_total{area}` counts it.
"""

from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import RateLimited
from app.core.metrics import RATE_LIMITED
from app.core.principal import Principal
from app.core.ratelimit import RateLimiter

CODE = "rate.limited"


class Area(StrEnum):
    WRITE = "write"
    UPLOAD = "upload"


def _limiter(session: AsyncSession, settings: Settings, area: Area) -> RateLimiter:
    limit = (
        settings.upload_rate_per_minute if area == Area.UPLOAD else settings.write_rate_per_minute
    )
    return RateLimiter(session, limit=limit)


def _key(writer: Principal, area: Area) -> str:
    return f"{area}:{writer}"


async def admit_now(
    session: AsyncSession, settings: Settings, writer: Principal, area: Area
) -> None:
    """Counts one write of `writer` and commits; 429 `rate.limited` beyond the limit."""
    limiter = _limiter(session, settings, area)
    key = _key(writer, area)
    if await limiter.acquire(key) is not None:
        return
    RATE_LIMITED.labels(area=area.value).inc()
    refused = RateLimited(code=CODE)
    refused.retry_after = await limiter.retry_after(key)
    raise refused


async def admit_within(
    session: AsyncSession, settings: Settings, writer: Principal, area: Area = Area.WRITE
) -> bool:
    """Counts one write of `writer` in the caller's transaction; whether it may write."""
    if await _limiter(session, settings, area).admit(_key(writer, area)) is not None:
        return True
    RATE_LIMITED.labels(area=area.value).inc()
    return False
