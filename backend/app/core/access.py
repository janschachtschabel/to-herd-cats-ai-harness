"""Who acts (`Actor`) and what they may do (`can`, `require`, `visible_space_ids`).

A stub until the central permission check (M1 Task 7) replaces the bodies; the
signatures are final. Rules so far:

- system admins and owners may do everything;
- members may create spaces;
- inside a space the role decides: `viewer` reads, `admin` manages. The role is the
  highest of the direct and the group memberships; in `open` spaces everyone but a
  guest is at least `viewer`.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, NotFound
from app.core.permissions import Action, SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.auth.context import AuthContext
from app.modules.groups.repository import GroupRepository
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository

__all__ = ["Action", "Actor", "actor_for", "can", "require", "space_role", "visible_space_ids"]

# The lowest space role an action needs.
_SPACE_ACTIONS = {Action.SPACE_READ: SpaceRole.VIEWER, Action.SPACE_MANAGE: SpaceRole.ADMIN}


@dataclass(frozen=True, slots=True)
class Actor:
    org_id: uuid.UUID
    principal: Principal
    system_role: SystemRole
    group_ids: frozenset[uuid.UUID]

    @property
    def is_admin(self) -> bool:
        return self.system_role in (SystemRole.OWNER, SystemRole.ADMIN)

    @property
    def principals(self) -> list[Principal]:
        """Whoever's memberships count for this actor: itself and its groups."""
        return [self.principal, *(Principal.group(g) for g in sorted(self.group_ids))]


async def actor_for(session: AsyncSession, auth: AuthContext) -> Actor:
    group_ids = await GroupRepository(session).group_ids_for(auth.principal)
    return Actor(auth.org_id, auth.principal, auth.system_role, group_ids)


def visible_space_ids(actor: Actor) -> Select[uuid.UUID]:
    """The ids of every space `actor` may read, as SQL for list filters."""
    return SpaceRepository.visible_ids_stmt(
        actor.org_id,
        None if actor.is_admin else actor.principals,
        include_open=actor.system_role != SystemRole.GUEST,
    )


async def space_role(session: AsyncSession, actor: Actor, space_id: uuid.UUID) -> SpaceRole | None:
    space = await SpaceRepository(session).get(actor.org_id, space_id)
    return None if space is None else await _role_in(session, actor, space)


async def can(
    session: AsyncSession, actor: Actor, action: Action, space_id: uuid.UUID | None = None
) -> bool:
    if action in _SPACE_ACTIONS and space_id is not None:
        space = await SpaceRepository(session).get(actor.org_id, space_id)
        if space is None:
            return False
        if actor.is_admin:
            return True
        role = await _role_in(session, actor, space)
        return role is not None and role >= _SPACE_ACTIONS[action]
    if actor.is_admin:
        return True
    return action is Action.SPACE_CREATE and actor.system_role == SystemRole.MEMBER


async def require(
    session: AsyncSession, actor: Actor, action: Action, space_id: uuid.UUID | None = None
) -> None:
    """A space the actor cannot see does not exist for them (404, as for an unknown id);
    a visible one without the right is 403."""
    if space_id is not None and not await can(session, actor, Action.SPACE_READ, space_id):
        raise NotFound(code="space.not_found")
    if not await can(session, actor, action, space_id):
        raise Forbidden(code="auth.permission_denied")


async def _role_in(session: AsyncSession, actor: Actor, space: Space) -> SpaceRole | None:
    roles = await SpaceRepository(session).roles_of(space.id, actor.principals)
    if space.kind == SpaceKind.OPEN and actor.system_role != SystemRole.GUEST:
        roles.append(SpaceRole.VIEWER)
    return max(roles, default=None)
