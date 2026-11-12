"""Sliding-window rate limiter backed by PostgreSQL.

Every API replica shares the same counters, so limits hold in a cluster. The
table is tiny: rows older than the window are pruned on each check. It is not
tenant data (a login attempt has no organisation yet), so it has no org_id.
"""

from datetime import datetime, timedelta

from sqlalchemy import DateTime, String, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, UuidPk, utcnow


class RateLimitHit(UuidPk, Base):
    __tablename__ = "rate_limit_hit"

    key: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    hit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RateLimiter:
    def __init__(self, session: AsyncSession, *, limit: int, window_seconds: int = 60) -> None:
        self.session = session
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)

    async def allow(self, key: str, now: datetime | None = None) -> bool:
        """Record a hit for `key` and report whether it is within the limit."""
        now = now or utcnow()
        cutoff = now - self.window
        await self.session.execute(
            delete(RateLimitHit).where(RateLimitHit.key == key, RateLimitHit.hit_at < cutoff)
        )
        count_stmt = (
            select(func.count())
            .select_from(RateLimitHit)
            .where(RateLimitHit.key == key, RateLimitHit.hit_at >= cutoff)
        )
        hits = int(await self.session.scalar(count_stmt) or 0)
        if hits >= self.limit:
            return False
        self.session.add(RateLimitHit(key=key, hit_at=now))
        # Commit immediately: the hit must survive even if the request then fails
        # (a rejected login is exactly what we count).
        await self.session.commit()
        return True
