"""Who acts: the principal, its organisation, and what it was when the request began."""

import uuid
from dataclasses import dataclass

from app.core.permissions import ADMIN_ROLES
from app.core.principal import Principal, SystemRole


@dataclass(frozen=True, slots=True)
class Actor:
    """A snapshot taken by `actor_for` at the start of a request (or, later, of a
    tool call). The permission check re-reads the system role and whether the person
    is still active; group memberships come from `group_ids`, so an actor that should
    see a group change is built anew."""

    org_id: uuid.UUID
    principal: Principal
    system_role: SystemRole
    group_ids: frozenset[uuid.UUID]

    @property
    def is_admin(self) -> bool:
        return self.system_role in ADMIN_ROLES

    @property
    def principals(self) -> list[Principal]:
        """Whoever's memberships count for this actor: itself and its groups."""
        return [self.principal, *(Principal.group(g) for g in sorted(self.group_ids))]
