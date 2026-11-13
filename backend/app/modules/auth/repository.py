import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def delete_by_hash(self, token_hash: str) -> None:
        await self.session.execute(delete(UserSession).where(UserSession.token_hash == token_hash))

    async def delete_expired(self, org_id: uuid.UUID, now: datetime, limit: int) -> None:
        """Up to `limit` expired sessions of the organisation, oldest first."""
        expired = (
            select(UserSession.id)
            .where(UserSession.org_id == org_id, UserSession.expires_at <= now)
            .order_by(UserSession.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        await self.session.execute(delete(UserSession).where(UserSession.id.in_(expired)))

    async def delete_for_user(
        self, org_id: uuid.UUID, user_id: uuid.UUID, *, keep: uuid.UUID | None = None
    ) -> None:
        """All of the person's sessions, except `keep` if given."""
        stmt = delete(UserSession).where(
            UserSession.org_id == org_id, UserSession.user_id == user_id
        )
        if keep is not None:
            stmt = stmt.where(UserSession.id != keep)
        await self.session.execute(stmt)
