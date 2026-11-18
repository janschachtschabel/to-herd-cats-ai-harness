"""SQL of the second factor's lasting lock (review M9b F9, `factor.py`): wrong codes
counted on the person's TOTP row, in one statement each, so concurrent failures all
count."""

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.totp.models import UserTotp


class TotpLockRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    def _row(self, user_id: uuid.UUID) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
        return (UserTotp.org_id == self.org_id, UserTotp.user_id == user_id)

    async def locked_until(self, user_id: uuid.UUID) -> datetime | None:
        return await self.session.scalar(select(UserTotp.locked_until).where(*self._row(user_id)))

    async def count_failure(self, user_id: uuid.UUID, now: datetime, window_start: datetime) -> int:
        """One more wrong code: a new window if the last began before `window_start`;
        the count in the window (0 without a TOTP row)."""
        fresh = UserTotp.failures_since.is_(None) | (UserTotp.failures_since < window_start)
        count = await self.session.scalar(
            update(UserTotp)
            .where(*self._row(user_id))
            .values(
                failures=case((fresh, 1), else_=UserTotp.failures + 1),
                failures_since=case((fresh, now), else_=UserTotp.failures_since),
            )
            .returning(UserTotp.failures)
        )
        return int(count or 0)

    async def lock(self, user_id: uuid.UUID, until: datetime) -> None:
        """Locked until `until`; the count starts again."""
        await self.session.execute(
            update(UserTotp)
            .where(*self._row(user_id))
            .values(locked_until=until, failures=0, failures_since=None)
        )

    async def reset(self, user_id: uuid.UUID) -> None:
        """A correct code: the count starts again."""
        await self.session.execute(
            update(UserTotp)
            .where(*self._row(user_id), UserTotp.failures > 0)
            .values(failures=0, failures_since=None)
        )
