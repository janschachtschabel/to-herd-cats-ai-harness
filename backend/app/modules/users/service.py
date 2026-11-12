"""People administration: create, change, deactivate, reactivate, list.

Writes for one organisation are serialised (`lock_admin_writes`), so the version check,
the email check and the last-owner rule hold under concurrent requests. Only an owner
grants or revokes the owner role, and only an owner changes an owner's password or
(de)activates an owner.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Forbidden, NotFound
from app.core.pagination import Page, PageParams, decode_id_cursor, encode_id_cursor
from app.core.principal import SystemRole
from app.core.security import hash_password
from app.modules.auth.context import AuthContext, ensure_can_manage_users
from app.modules.auth.repository import SessionRepository
from app.modules.spaces.service import SpaceService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)

    async def create(self, actor: AuthContext, data: UserCreate) -> User:
        """The person and, in the same transaction, their personal space."""
        ensure_can_manage_users(actor)
        if data.system_role == SystemRole.OWNER:
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
            password_hash=hash_password(data.password) if data.password else None,
        )
        await self.users.add(user)
        await SpaceService(self.users.session).create_personal(user)
        return user

    async def update(
        self, actor: AuthContext, user_id: uuid.UUID, data: UserUpdate, version: int
    ) -> User:
        """A new password ends all of the person's sessions."""
        ensure_can_manage_users(actor)
        user = await self._current(actor, user_id)
        role_changes = data.system_role not in (None, user.system_role)
        if role_changes and SystemRole.OWNER in (data.system_role, user.system_role):
            _owner_only(actor)
        if data.password is not None and user.system_role == SystemRole.OWNER:
            _owner_only(actor)
        if user.version != version:
            raise Conflict(code="users.version_conflict")
        if data.system_role not in (None, SystemRole.OWNER):
            await self._keep_an_owner(user)
        if data.name is not None:
            user.name = data.name
        if data.system_role is not None:
            user.system_role = data.system_role
        if data.locale is not None:
            user.locale = data.locale
        if data.password is not None:
            user.password_hash = hash_password(data.password)
            await self.sessions.delete_for_user(actor.org_id, user.id)
        user.version += 1
        await self.users.session.flush()
        return user

    async def deactivate(self, actor: AuthContext, user_id: uuid.UUID) -> None:
        """Deactivated people are logged out at once: all their sessions are deleted."""
        user = await self._activity_target(actor, user_id)
        await self._keep_an_owner(user)
        if user.is_active:
            user.is_active = False
            user.version += 1
        await self.sessions.delete_for_user(actor.org_id, user.id)
        await self.users.session.flush()

    async def reactivate(self, actor: AuthContext, user_id: uuid.UUID) -> None:
        """The person can log in again; idempotent."""
        user = await self._activity_target(actor, user_id)
        if not user.is_active:
            user.is_active = True
            user.version += 1
        await self.users.session.flush()

    async def list(self, actor: AuthContext, params: PageParams) -> Page[User]:
        ensure_can_manage_users(actor)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.users.page(actor.org_id, after, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        return Page[User](items=items, next_cursor=encode_id_cursor(items[-1].id) if more else None)

    async def _current(self, actor: AuthContext, user_id: uuid.UUID) -> User:
        """The person as committed now, with the organisation's admin writes locked."""
        await self.users.lock_admin_writes(actor.org_id)
        user = await self.users.get_current(actor.org_id, user_id)
        if user is None:
            raise NotFound(code="users.not_found")
        return user

    async def _activity_target(self, actor: AuthContext, user_id: uuid.UUID) -> User:
        ensure_can_manage_users(actor)
        user = await self._current(actor, user_id)
        if user.system_role == SystemRole.OWNER:
            _owner_only(actor)
        return user

    async def _keep_an_owner(self, user: User) -> None:
        """`user` is about to stop being an active owner: there must be another one."""
        if user.system_role != SystemRole.OWNER or not user.is_active:
            return
        if await self.users.count_active_owners(user.org_id) <= 1:
            raise Conflict(code="users.last_owner")


def _owner_only(actor: AuthContext) -> None:
    if actor.system_role != SystemRole.OWNER:
        raise Forbidden(code="users.owner_only")
