"""Sliding-window rate limiter backed by PostgreSQL.

Every API replica shares the same counters, so limits hold in a cluster. It is not
tenant data (a login attempt has no organisation yet), so the table has no org_id.

- Atomic per key: a transaction-level advisory lock on the key serialises count and
  insert, so concurrent attempts cannot all pass the count before any of them is
  recorded.
- Every limiter uses the same window (`WINDOW`); each check also deletes up to
  `PRUNE_BATCH` rows older than it, of any key, so keys that are never used again do
  not stay (index on `hit_at`).
- A hit can be released again (`release`): the login limit counts only failures.
- Limits per client address use `limit_key`: an IPv4 address as it is, an IPv6 address
  by its /64 (one host normally controls a whole /64). The audit log keeps the full
  address.
"""

import ipaddress
import uuid
from datetime import datetime, timedelta

from sqlalchemy import DateTime, String, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, UuidPk, utcnow
from app.core.repository import advisory_xact_lock

WINDOW = timedelta(seconds=60)
PRUNE_BATCH = 500


def limit_key(address: str | None) -> str:
    """The part of a client address a per-address limit counts by."""
    if address is None:
        return "unknown"
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((ip, 64), strict=False))
    return str(ip)


class RateLimitHit(UuidPk, Base):
    __tablename__ = "rate_limit_hit"

    key: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    hit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class RateLimiter:
    def __init__(self, session: AsyncSession, *, limit: int) -> None:
        self.session = session
        self.limit = limit

    async def acquire(self, key: str, now: datetime | None = None) -> uuid.UUID | None:
        """Record a hit for `key` if it is within the limit: its id, else None.

        Commits at once: the hit must survive even if the request then fails (a
        rejected login is exactly what is counted), and the commit ends the lock."""
        now = now or utcnow()
        cutoff = now - WINDOW
        await advisory_xact_lock(self.session, f"ratelimit:{key}")
        await self._prune(cutoff)
        count_stmt = (
            select(func.count())
            .select_from(RateLimitHit)
            .where(RateLimitHit.key == key, RateLimitHit.hit_at >= cutoff)
        )
        hits = int(await self.session.scalar(count_stmt) or 0)
        if hits >= self.limit:
            await self.session.commit()
            return None
        hit = RateLimitHit(key=key, hit_at=now)
        self.session.add(hit)
        await self.session.commit()
        return hit.id

    async def release(self, hit_id: uuid.UUID) -> None:
        """Take a hit back (it did not count); part of the caller's transaction."""
        await self.session.execute(delete(RateLimitHit).where(RateLimitHit.id == hit_id))

    async def _prune(self, cutoff: datetime) -> None:
        stale = (
            select(RateLimitHit.id)
            .where(RateLimitHit.hit_at < cutoff)
            .limit(PRUNE_BATCH)
            .with_for_update(skip_locked=True)
        )
        await self.session.execute(delete(RateLimitHit).where(RateLimitHit.id.in_(stale)))
