"""Who acts: the principal, its organisation, and what it was when the request began."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from app.core.permissions import ADMIN_ROLES, SpaceRole
from app.core.principal import Principal, SystemRole


@dataclass(frozen=True, slots=True)
class ReadScope:
    """The most an actor may do per space, on top of its own rights (spec 5.6): a space
    not listed is not there for it, and in a listed one its role is at most the one
    given. An agent's run acts as the person who asked, held to what the agent itself
    may do (`modules/agents/actor.py`); the check (`core/access.py`) applies it to
    whatever actor carries it, without knowing why."""

    roles: frozenset[tuple[uuid.UUID, SpaceRole]]

    @classmethod
    def of(cls, roles: Mapping[uuid.UUID, SpaceRole]) -> "ReadScope":
        return cls(frozenset(roles.items()))

    def cap(self, space_id: uuid.UUID) -> SpaceRole | None:
        return next((role for sid, role in self.roles if sid == space_id), None)

    def ids(self, min_role: SpaceRole = SpaceRole.VIEWER) -> list[uuid.UUID]:
        """The spaces where the scope allows at least `min_role`, sorted."""
        return sorted(sid for sid, role in self.roles if role >= min_role)


@dataclass(frozen=True, slots=True)
class Actor:
    """A snapshot taken by `actor_for` at the start of a request (or, later, of a
    tool call). The permission check re-reads the system role and whether the person
    is still active; group memberships come from `group_ids`, so an actor that should
    see a group change is built anew. `read_scope`, when set, narrows every check and
    every list filter (see `ReadScope`)."""

    org_id: uuid.UUID
    principal: Principal
    system_role: SystemRole
    group_ids: frozenset[uuid.UUID]
    read_scope: ReadScope | None = None

    @property
    def is_admin(self) -> bool:
        return self.system_role in ADMIN_ROLES

    @property
    def principals(self) -> list[Principal]:
        """Whoever's memberships count for this actor: itself and its groups."""
        return [self.principal, *(Principal.group(g) for g in sorted(self.group_ids))]
