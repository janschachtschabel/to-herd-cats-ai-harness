"""Who acts (`Actor`) and what they may do (`can`, `require`).

A stub until the central permission check (M1 Task 7) replaces the body of `can`:
system admins may do everything, members may create spaces, nothing else is granted.
The signatures are final.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden
from app.core.permissions import Action
from app.core.principal import Principal, SystemRole
from app.modules.auth.context import AuthContext
from app.modules.groups.repository import GroupRepository

__all__ = ["Action", "Actor", "actor_for", "can", "require"]


@dataclass(frozen=True, slots=True)
class Actor:
    org_id: uuid.UUID
    principal: Principal
    system_role: SystemRole
    group_ids: frozenset[uuid.UUID]

    @property
    def is_admin(self) -> bool:
        return self.system_role in (SystemRole.OWNER, SystemRole.ADMIN)


async def actor_for(session: AsyncSession, auth: AuthContext) -> Actor:
    group_ids = await GroupRepository(session).group_ids_for(auth.principal)
    return Actor(auth.org_id, auth.principal, auth.system_role, group_ids)


async def can(
    session: AsyncSession, actor: Actor, action: Action, space_id: uuid.UUID | None = None
) -> bool:
    if actor.is_admin:
        return True
    return action is Action.SPACE_CREATE and actor.system_role == SystemRole.MEMBER


async def require(
    session: AsyncSession, actor: Actor, action: Action, space_id: uuid.UUID | None = None
) -> None:
    if not await can(session, actor, action, space_id):
        raise Forbidden(code="auth.permission_denied")
