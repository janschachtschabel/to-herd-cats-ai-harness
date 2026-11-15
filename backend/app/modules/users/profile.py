"""What a person changes about themselves: their language and their password.

No right is needed beyond acting at all (a deactivated person does not act). The
person's row is locked like an administrator's change of it, so the version check
holds against both. A password change needs the current password (failed attempts
are limited like logins) and ends every other session of the person; its hashing
runs with no connection and no lock held (checked again under the lock afterwards).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import Conflict, NotFound, RateLimited, ValidationFailed
from app.core.ratelimit import RateLimiter
from app.core.security import hash_password_async, verify_password_async
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.auth.repository import SessionRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import ProfileUpdate


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def update(self, actor: Actor, data: ProfileUpdate, version: int) -> User:
        user = await self._me(actor)
        if user.version != version:
            raise Conflict(code="users.version_conflict")
        before = snapshot(user, ("locale",))
        user.locale = data.locale
        if changed := changes(before, user):
            user.version += 1
            await self.session.flush()
            await record(self.session, actor, "user.updated", "user", user.id, {"changes": changed})
        return user

    async def change_password(
        self,
        actor: Actor,
        current: str,
        new: str,
        *,
        keep_session: uuid.UUID | None,
        failures_per_minute: int,
    ) -> None:
        limiter = RateLimiter(self.session, limit=failures_per_minute)
        attempt = await limiter.acquire(f"password-fail:{actor.principal.id}")  # commits
        if attempt is None:
            raise RateLimited(code="auth.too_many_attempts")
        user = await self.users.get_current(actor.org_id, actor.principal.id)
        if user is None:  # an agent, or a person deleted meanwhile
            raise NotFound(code="users.not_found")
        checked = user.password_hash
        # Hash with no connection and no lock held; take the lock afterwards.
        await self.session.commit()
        if checked is None or not await verify_password_async(checked, current):
            raise ValidationFailed(code="auth.wrong_password")
        new_hash = await hash_password_async(new)
        user = await self._me(actor)
        if user.password_hash != checked:  # changed meanwhile (another tab, an admin)
            raise Conflict(code="users.version_conflict")
        await limiter.release(attempt)
        user.password_hash = new_hash
        user.version += 1
        await self.session.flush()
        await SessionRepository(self.session).delete_for_user(
            actor.org_id, user.id, keep=keep_session
        )
        await record(self.session, actor, "user.password_changed", "user", user.id)

    async def _me(self, actor: Actor) -> User:
        await self.users.lock_admin_writes(actor.org_id)
        user = await self.users.get_current(actor.org_id, actor.principal.id)
        if user is None:  # an agent, or a person deleted meanwhile
            raise NotFound(code="users.not_found")
        return user
