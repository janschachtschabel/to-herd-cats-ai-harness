import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import locked_batch
from app.modules.auth.models import UserSession


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        await self.session.flush()
        return user_session

    async def get_active(self, token_hash: str, now: datetime) -> UserSession | None:
        stmt = select(UserSession).where(
            UserSession.token_hash == token_hash, UserSession.expires_at > now
        )
        return await self.session.scalar(stmt)

    async def get_active_by_id(self, session_id: uuid.UUID, now: datetime) -> UserSession | None:
        stmt = select(UserSession).where(UserSession.id == session_id, UserSession.expires_at > now)
        return await self.session.scalar(stmt)

    async def get_by_id(self, session_id: uuid.UUID) -> UserSession | None:
        """Active or ended (until it is cleared away)."""
        return await self.session.scalar(select(UserSession).where(UserSession.id == session_id))

    async def end_by_hash(self, token_hash: str, now: datetime) -> uuid.UUID | None:
        """The session ends now; the row stays until `delete_expired` clears it. The
        person whose session it was, None if no running session had this hash."""
        ended: uuid.UUID | None = await self.session.scalar(
            update(UserSession)
            .where(UserSession.token_hash == token_hash, UserSession.expires_at > now)
            .values(expires_at=now)
            .returning(UserSession.user_id)
        )
        return ended

    async def delete_expired(self, org_id: uuid.UUID, before: datetime, limit: int) -> None:
        """Up to `limit` sessions of the organisation that ended before `before`,
        oldest first."""
        doomed = locked_batch(
            select(UserSession.id)
            .where(UserSession.org_id == org_id, UserSession.expires_at <= before)
            .order_by(UserSession.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True),
            "doomed",
        )
        await self.session.execute(delete(UserSession).where(UserSession.id == doomed.c.id))

    async def delete_for_user(
        self, org_id: uuid.UUID, user_id: uuid.UUID, *, keep: uuid.UUID | None = None
    ) -> None:
        """All of the person's sessions, except `keep` if given."""
        await self.delete_for_users(org_id, [user_id], keep=keep)

    async def delete_for_users(
        self, org_id: uuid.UUID, user_ids: Sequence[uuid.UUID], *, keep: uuid.UUID | None = None
    ) -> None:
        """All of these people's sessions, except `keep` if given."""
        if not user_ids:
            return
        stmt = delete(UserSession).where(
            UserSession.org_id == org_id, UserSession.user_id.in_(user_ids)
        )
        if keep is not None:
            stmt = stmt.where(UserSession.id != keep)
        await self.session.execute(stmt)
