"""The one permission check (spec 4.2). Every service asks `require` (or `can`); there
is no other place that decides who may do what.

- System admins and owners may do everything, in every space of their organisation.
- System-wide actions follow the system role (`SYSTEM_ROLE_ACTIONS`).
- Inside a space the effective role decides: the highest of the actor's direct role
  and its groups' roles; in `open` spaces everyone but a guest is at least `viewer`.
- A space the actor may not read does not exist for it: `require` answers 404 as for
  an unknown id, and 403 only where the space is visible but the right is missing.
- When an admin gets into a team or personal space only through admin power (no
  membership of their own or through a group), `require` notes it in the audit log
  (spec 5.5), at most once per admin, space and UTC day. `can` only answers.

Each check is one SQL query (`AccessRepository.facts`); lists filter with the SQL of
`visible_space_ids`, which the check itself uses for readability.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_repository import (
    AccessFacts,
    AccessRepository,
    ids_with_role_stmt,
    visible_ids_stmt,
)
from app.core.actor import Actor
from app.core.errors import Forbidden, NotFound, Unauthorized
from app.core.permissions import (
    ADMIN_ROLES,
    OPEN_SPACE_FLOOR,
    OPEN_SPACE_READERS,
    SPACE_ACTION_MIN_ROLE,
    SYSTEM_ROLE_ACTIONS,
    Action,
    SpaceRole,
)
from app.modules.audit.recorder import record_admin_access
from app.modules.auth.context import AuthContext
from app.modules.groups.repository import GroupRepository
from app.modules.spaces.models import SpaceKind

# Spaces an admin may open without a membership, but not unnoticed.
ADMIN_ACCESS_AUDITED_KINDS = frozenset({SpaceKind.TEAM, SpaceKind.PERSONAL})

__all__ = [
    "Action",
    "Actor",
    "actor_for",
    "can",
    "my_roles",
    "require",
    "space_ids_with",
    "space_role",
    "system_permissions",
    "visible_space_ids",
]


async def actor_for(session: AsyncSession, auth: AuthContext) -> Actor:
    """The caller as the check sees them. A deactivated person does not act."""
    if not auth.user.is_active:
        raise Unauthorized(code="auth.session_invalid")
    group_ids = await GroupRepository(session).group_ids_for(auth.principal)
    return Actor(auth.org_id, auth.principal, auth.system_role, group_ids)


def visible_space_ids(actor: Actor) -> Select[uuid.UUID]:
    """The ids of every space `actor` may read, as SQL for list filters."""
    return visible_ids_stmt(actor)


def space_ids_with(actor: Actor, action: Action) -> Select[uuid.UUID]:
    """The ids of every space where `actor` may do the space action, as SQL for list
    filters (`can` for each space, in one statement)."""
    return ids_with_role_stmt(actor, SPACE_ACTION_MIN_ROLE[action])


async def space_role(session: AsyncSession, actor: Actor, space_id: uuid.UUID) -> SpaceRole | None:
    """The actor's effective role in the space; None without one (admins included)."""
    return _effective_role(await AccessRepository(session).facts(actor, space_id))


async def system_permissions(session: AsyncSession, actor: Actor) -> list[Action]:
    """The system-wide actions the actor holds now, sorted; none once it no longer acts.
    Space-scoped actions are not listed: they depend on the space (see `my_roles`)."""
    role = (await AccessRepository(session).facts(actor, None)).system_role
    if role is None:
        return []
    held = (a for a in SYSTEM_ROLE_ACTIONS[role] if a not in SPACE_ACTION_MIN_ROLE)
    return sorted(held, key=lambda a: a.value)


async def my_roles(
    session: AsyncSession, actor: Actor, space_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, SpaceRole | None]:
    """The role to show the actor for each space, in one query: the effective role, and
    `admin` for system admins and owners, who hold every right in every space (E4).
    For display only; decisions go through `can` and `require`."""
    if not space_ids:
        return {}
    facts = await AccessRepository(session).facts_in(actor, space_ids)
    return {space_id: _shown_role(facts[space_id]) for space_id in space_ids if space_id in facts}


async def can(
    session: AsyncSession, actor: Actor, action: Action, space_id: uuid.UUID | None = None
) -> bool:
    if action in SPACE_ACTION_MIN_ROLE and space_id is None:
        return False
    scoped = space_id if action in SPACE_ACTION_MIN_ROLE else None
    return _allows(await AccessRepository(session).facts(actor, scoped), action)


async def require(
    session: AsyncSession, actor: Actor, action: Action, space_id: uuid.UUID | None = None
) -> None:
    """Raise unless the actor may do `action` (in the space, if given)."""
    facts = await AccessRepository(session).facts(actor, space_id)
    if space_id is not None and not facts.readable:
        raise NotFound(code="space.not_found")
    if not _allows(facts, action):
        raise Forbidden(code="auth.permission_denied")
    if space_id is not None and facts.kind is not None and _by_admin_power(facts):
        await record_admin_access(session, actor, space_id, facts.kind)


def _by_admin_power(facts: AccessFacts) -> bool:
    return (
        facts.system_role in ADMIN_ROLES
        and facts.kind in ADMIN_ACCESS_AUDITED_KINDS
        and facts.member_role is None
    )


def _shown_role(facts: AccessFacts) -> SpaceRole | None:
    if facts.system_role in ADMIN_ROLES:
        return SpaceRole.ADMIN
    return _effective_role(facts)


def _effective_role(facts: AccessFacts) -> SpaceRole | None:
    if facts.system_role is None or facts.kind is None:
        return None
    opens = facts.kind == SpaceKind.OPEN and facts.system_role in OPEN_SPACE_READERS
    roles = [r for r in (facts.member_role, OPEN_SPACE_FLOOR if opens else None) if r]
    return max(roles, default=None)


def _allows(facts: AccessFacts, action: Action) -> bool:
    if facts.system_role is None:
        return False
    if action not in SPACE_ACTION_MIN_ROLE:
        return action in SYSTEM_ROLE_ACTIONS[facts.system_role]
    if not facts.readable:
        return False
    if facts.system_role in ADMIN_ROLES:
        return True
    role = _effective_role(facts)
    return role is not None and role >= SPACE_ACTION_MIN_ROLE[action]
