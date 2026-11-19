import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, delete, or_, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import locked_batch
from app.modules.auth.models import UserSession
from app.modules.totp.repository import ChallengeRepository

# A session's last use is written at most this often (J7).
TOUCH_EVERY = timedelta(minutes=1)


def running(now: datetime, idle: timedelta | None) -> ColumnElement[bool]:
    """A session that has not expired and, with an idle limit, was used within it."""
    alive = UserSession.expires_at > now
    if idle is None:
        return alive
    return alive & (UserSession.last_used_at > now - idle)


class SessionRepository:
    def __init__(self, session: AsyncSession, idle: timedelta | None = None) -> None:
        """`idle`: the idle limit (HERD_SESSION_IDLE_HOURS), None for none."""
        self.session = session
        self.idle = idle

    async def add(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        await self.session.flush()
        return user_session

    async def get_active(self, token_hash: str, now: datetime) -> UserSession | None:
        stmt = select(UserSession).where(
            UserSession.token_hash == token_hash, running(now, self.idle)
        )
        return await self.session.scalar(stmt)

    async def get_active_by_id(self, session_id: uuid.UUID, now: datetime) -> UserSession | None:
        stmt = select(UserSession).where(UserSession.id == session_id, running(now, self.idle))
        return await self.session.scalar(stmt)

    async def touch(self, session_id: uuid.UUID, now: datetime) -> bool:
        """Note the session's use now, if its last one is at least `TOUCH_EVERY` ago;
        never waits for a row another transaction holds (that one is in use anyway).
        Whether it wrote."""
        due = locked_batch(
            select(UserSession.id)
            .where(UserSession.id == session_id, UserSession.last_used_at <= now - TOUCH_EVERY)
            .with_for_update(skip_locked=True),
            "due",
        )
        touched = await self.session.scalar(
            update(UserSession)
            .where(UserSession.id == due.c.id)
            .values(last_used_at=now)
            .returning(UserSession.id)
        )
        return touched is not None

    async def end_idle(
        self, now: datetime, *, token_hash: str | None = None, limit: int = 1
    ) -> int:
        """Record the end of up to `limit` sessions (with this token, if given) that the idle limit
        ended: their expiry becomes the moment they went idle, as a sign-out ends a
        session, so a longer or no idle limit later does not revive them (R18-3). How
        many."""
        if self.idle is None:
            return 0
        stmt = select(UserSession.id).where(
            UserSession.expires_at > now, UserSession.last_used_at <= now - self.idle
        )
        if token_hash is not None:
            stmt = stmt.where(UserSession.token_hash == token_hash)
        idle = locked_batch(stmt.limit(limit).with_for_update(skip_locked=True), "idle")
        ended = await self.session.scalars(
            update(UserSession)
            .where(UserSession.id == idle.c.id)
            .values(expires_at=UserSession.last_used_at + self.idle)
            .returning(UserSession.id)
        )
        return len(ended.all())

    def ended(self, user_session: UserSession, now: datetime) -> bool:
        """The session has ended: expired, logged out or idle too long."""
        if user_session.expires_at <= now:
            return True
        return self.idle is not None and user_session.last_used_at <= now - self.idle

    async def get_by_id(self, session_id: uuid.UUID) -> UserSession | None:
        """Active or ended (until it is cleared away)."""
        return await self.session.scalar(select(UserSession).where(UserSession.id == session_id))

    async def end_by_hash(self, token_hash: str, now: datetime) -> uuid.UUID | None:
        """The session ends now; the row stays until `delete_expired` clears it. The
        person whose session it was, None if no session with this hash was still to
        end. A session the idle limit ended whose end is not recorded yet ends too
        (R18-3)."""
        ended: uuid.UUID | None = await self.session.scalar(
            update(UserSession)
            .where(UserSession.token_hash == token_hash, UserSession.expires_at > now)
            .values(expires_at=now)
            .returning(UserSession.user_id)
        )
        return ended

    async def delete_expired(self, org_id: uuid.UUID, before: datetime, limit: int) -> None:
        """Up to `limit` sessions of the organisation that ended before `before` (by
        expiry or, with an idle limit, by idleness), oldest first."""
        ended = UserSession.expires_at <= before
        if self.idle is not None:
            ended = or_(ended, UserSession.last_used_at <= before - self.idle)
        doomed = locked_batch(
            select(UserSession.id)
            .where(UserSession.org_id == org_id, ended)
            .order_by(UserSession.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True),
            "doomed",
        )
        await self.session.execute(delete(UserSession).where(UserSession.id == doomed.c.id))

    async def delete_for_user(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        keep: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> int:
        """All of the person's sessions, except `keep` if given; how many there were
        (with `now`: how many of them were still running)."""
        return await self.delete_for_users(org_id, [user_id], keep=keep, now=now)

    async def delete_for_users(
        self,
        org_id: uuid.UUID,
        user_ids: Sequence[uuid.UUID],
        *,
        keep: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> int:
        """All of these people's sessions, except `keep` if given, and every sign-in of
        theirs that waits for the second factor; how many sessions there were (with
        `now`: how many of them were still running, R18-11)."""
        if not user_ids:
            return 0
        await ChallengeRepository(self.session).delete_for_users(org_id, user_ids)
        stmt = delete(UserSession).where(
            UserSession.org_id == org_id, UserSession.user_id.in_(user_ids)
        )
        if keep is not None:
            stmt = stmt.where(UserSession.id != keep)
        counted = running(now, self.idle) if now is not None else true()
        deleted = await self.session.scalars(stmt.returning(counted))
        return sum(1 for alive in deleted.all() if alive)

    async def note_device(self, token_hash: str, device: str | None) -> None:
        """The device hint of the session just opened with this token."""
        await self.session.execute(
            update(UserSession).where(UserSession.token_hash == token_hash).values(device=device)
        )

    async def list_running(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        now: datetime,
        *,
        before: uuid.UUID | None,
        limit: int,
    ) -> Sequence[UserSession]:
        """The person's running sessions, newest first (ids are UUIDv7), those older
        than `before` if given."""
        stmt = (
            select(UserSession)
            .where(
                UserSession.org_id == org_id,
                UserSession.user_id == user_id,
                running(now, self.idle),
            )
            .order_by(UserSession.id.desc())
            .limit(limit)
        )
        if before is not None:
            stmt = stmt.where(UserSession.id < before)
        return (await self.session.scalars(stmt)).all()

    async def delete_own(
        self, org_id: uuid.UUID, user_id: uuid.UUID, session_id: uuid.UUID, now: datetime
    ) -> bool:
        """The person's running session with this id ends (its row goes); whether there
        was one."""
        deleted = await self.session.scalar(
            delete(UserSession)
            .where(
                UserSession.id == session_id,
                UserSession.org_id == org_id,
                UserSession.user_id == user_id,
                running(now, self.idle),
            )
            .returning(UserSession.id)
        )
        return deleted is not None
