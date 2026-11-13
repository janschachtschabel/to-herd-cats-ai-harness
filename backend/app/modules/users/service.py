"""People administration: create, change, deactivate, reactivate, list.

Every change is audited in the transaction that makes it. Writes for one organisation
are serialised (`lock_admin_writes`), so the version check, the email check and the
last-owner rule hold under concurrent requests. Only an owner grants or revokes the
owner role, and only an owner changes an owner's password or (de)activates an owner.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.core.principal import SystemRole
from app.core.security import hash_password_async
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.auth.repository import SessionRepository
from app.modules.spaces.service import SpaceService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserUpdate

# What `user.updated` reports; a password change is its own entry, without values.
_AUDITED_FIELDS = ("name", "system_role", "locale")


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)

    async def create(self, actor: Actor, data: UserCreate) -> User:
        """The person and, in the same transaction, their personal space."""
        await require(self.session, actor, Action.USER_MANAGE)
        if _is_owner(data.system_role):
            _owner_only(actor)
        await self.users.lock_admin_writes(actor.org_id)
        if await self.users.get_by_email(actor.org_id, data.email):
            raise Conflict(code="users.email_taken")
        user = User(
            org_id=actor.org_id,
            email=data.email.lower(),
            name=data.name,
            locale=data.locale,
            system_role=data.system_role,
            password_hash=await hash_password_async(data.password) if data.password else None,
        )
        await self.users.add(user)
        await SpaceService(self.session).create_personal(user)
        await self._audit(actor, "user.created", user, {"system_role": user.system_role})
        return user

    async def update(
        self,
        actor: Actor,
        user_id: uuid.UUID,
        data: UserUpdate,
        version: int,
        *,
        current_session: uuid.UUID | None = None,
    ) -> User:
        """A new password ends the person's sessions; someone changing their own keeps
        `current_session`, the one they are making the change with."""
        await require(self.session, actor, Action.USER_MANAGE)
        user = await self._current(actor, user_id)
        role_changes = data.system_role is not None and data.system_role != user.system_role
        if role_changes and (_is_owner(data.system_role) or _is_owner(user.system_role)):
            _owner_only(actor)
        if data.password is not None and _is_owner(user.system_role):
            _owner_only(actor)
        if user.version != version:
            raise Conflict(code="users.version_conflict")
        if data.system_role is not None and not _is_owner(data.system_role):
            await self._keep_an_owner(user)
        before = snapshot(user, _AUDITED_FIELDS)
        if data.name is not None:
            user.name = data.name
        if data.system_role is not None:
            user.system_role = data.system_role
        if data.locale is not None:
            user.locale = data.locale
        if data.password is not None:
            user.password_hash = await hash_password_async(data.password)
            keep = current_session if actor.principal.id == user.id else None
            await self.sessions.delete_for_user(actor.org_id, user.id, keep=keep)
        user.version += 1
        await self.session.flush()
        if changed := changes(before, user):
            await self._audit(actor, "user.updated", user, {"changes": changed})
        if data.password is not None:
            await self._audit(actor, "user.password_changed", user)
        return user

    async def deactivate(self, actor: Actor, user_id: uuid.UUID) -> None:
        """Deactivated people are logged out at once: all their sessions are deleted."""
        user = await self._activity_target(actor, user_id)
        await self._keep_an_owner(user)
        await self.sessions.delete_for_user(actor.org_id, user.id)
        if user.is_active:
            user.is_active = False
            user.version += 1
            await self.session.flush()
            await self._audit(actor, "user.deactivated", user)

    async def reactivate(self, actor: Actor, user_id: uuid.UUID) -> None:
        """The person can log in again; idempotent."""
        user = await self._activity_target(actor, user_id)
        if not user.is_active:
            user.is_active = True
            user.version += 1
            await self.session.flush()
            await self._audit(actor, "user.reactivated", user)

    async def list(self, actor: Actor, params: PageParams) -> Page[User]:
        await require(self.session, actor, Action.USER_MANAGE)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.users.page(actor.org_id, after, params.limit + 1)
        return id_page(rows, params.limit, lambda u: u.id)

    async def _audit(
        self, actor: Actor, action: str, user: User, details: dict[str, Any] | None = None
    ) -> None:
        await record(self.session, actor, action, "user", user.id, details)

    async def _current(self, actor: Actor, user_id: uuid.UUID) -> User:
        """The person as committed now, with the organisation's admin writes locked."""
        await self.users.lock_admin_writes(actor.org_id)
        user = await self.users.get_current(actor.org_id, user_id)
        if user is None:
            raise NotFound(code="users.not_found")
        return user

    async def _activity_target(self, actor: Actor, user_id: uuid.UUID) -> User:
        await require(self.session, actor, Action.USER_MANAGE)
        user = await self._current(actor, user_id)
        if _is_owner(user.system_role):
            _owner_only(actor)
        return user

    async def _keep_an_owner(self, user: User) -> None:
        """`user` is about to stop being an active owner: there must be another one."""
        if not _is_owner(user.system_role) or not user.is_active:
            return
        if await self.users.count_active_owners(user.org_id) <= 1:
            raise Conflict(code="users.last_owner")


def _is_owner(role: SystemRole | str | None) -> bool:
    """The owner role is a business rule of the people administration, on top of
    `user.manage`: only an owner grants, revokes or touches it."""
    return role == SystemRole.OWNER


def _owner_only(actor: Actor) -> None:
    if not _is_owner(actor.system_role):
        raise Forbidden(code="users.owner_only")
