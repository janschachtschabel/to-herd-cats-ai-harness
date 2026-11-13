"""A limit on failed attempts (wrong passwords) that counts only completed failures.

An attempt reserves a place before the password is checked (a `pending:` row) and
turns into a failure only when the check fails; a success just drops the reservation.
So the limit stays exact under concurrency (20 parallel wrong passwords → exactly
`limit` of them are checked), and correct attempts in flight never use it up: an
attempt that finds `failures + pending >= limit` but `failures < limit` waits until
the attempts in flight have ended, then decides. It waits without a database
connection or lock (commit, sleep, look again), up to `max_wait`.

Rows live in the rate limiter's table and window (`ratelimit.WINDOW`), so they are
pruned like every other counter. A reservation whose request died counts until the
window passes it, as if it had failed.
"""

import asyncio
import time
import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.core.ratelimit import WINDOW, RateLimitHit, prune_stale
from app.core.repository import advisory_xact_lock

PENDING = "pending:"


class FailureLimiter:
    def __init__(
        self,
        session: AsyncSession,
        key: str,
        *,
        limit: int,
        max_wait: float = 5.0,
        poll: float = 0.05,
    ) -> None:
        self.session = session
        self.key = key
        self.limit = limit
        self.max_wait = max_wait
        self.poll = poll

    async def begin(self) -> uuid.UUID | None:
        """A reservation for one attempt, or None when the failures have reached the
        limit (or the attempts in flight did not end within `max_wait`). Commits."""
        deadline = time.monotonic() + self.max_wait
        while True:
            now = utcnow()
            await self._lock(now)
            failures = await self._count(self.key, now)
            pending = await self._count(PENDING + self.key, now)
            if failures >= self.limit:
                await self.session.commit()
                return None
            if failures + pending < self.limit:
                hit = RateLimitHit(key=PENDING + self.key, hit_at=now)
                self.session.add(hit)
                await self.session.commit()
                return hit.id
            await self.session.commit()  # no connection, no lock while waiting
            if time.monotonic() >= deadline:
                return None
            await asyncio.sleep(self.poll)

    async def fail(self, attempt: uuid.UUID) -> None:
        """The attempt failed: it counts from now on. Commits at once, so the failure
        survives the error the request then answers with."""
        now = utcnow()
        await self._lock(now)
        await self._drop(attempt)
        self.session.add(RateLimitHit(key=self.key, hit_at=now))
        await self.session.commit()

    async def end(self, attempt: uuid.UUID) -> None:
        """The attempt did not fail (or did not happen): drop the reservation, as part
        of the caller's transaction."""
        await self._drop(attempt)

    async def _lock(self, now: datetime) -> None:
        await advisory_xact_lock(self.session, f"ratelimit:{self.key}")
        await prune_stale(self.session, now - WINDOW)

    async def _count(self, key: str, now: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(RateLimitHit)
            .where(RateLimitHit.key == key, RateLimitHit.hit_at >= now - WINDOW)
        )
        return int(await self.session.scalar(stmt) or 0)

    async def _drop(self, attempt: uuid.UUID) -> None:
        await self.session.execute(delete(RateLimitHit).where(RateLimitHit.id == attempt))
