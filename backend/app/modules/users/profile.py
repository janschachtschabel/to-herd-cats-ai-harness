"""What a person changes about themselves: their language (and, later, more).

No right is needed beyond acting at all (a deactivated person does not act). The
person's row is locked like an administrator's change of it, so the version check
holds against both.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import Conflict, NotFound
from app.modules.audit.recorder import changes, record, snapshot
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

    async def _me(self, actor: Actor) -> User:
        await self.users.lock_admin_writes(actor.org_id)
        user = await self.users.get_current(actor.org_id, actor.principal.id)
        if user is None:  # an agent, or a person deleted meanwhile
            raise NotFound(code="users.not_found")
        return user
