"""Who acts: the principal, its organisation, and what it was when the request began."""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.core.permissions import ADMIN_ROLES, SpaceRole
from app.core.principal import Principal, SystemRole


@dataclass(frozen=True, slots=True)
class ReadScope:
    """The most an actor may do per space, on top of its own rights (spec 5.6): a space
    not listed is not there for it, and in a listed one its role is at most the one
    given. An agent's run acts as the person who asked, held to what the agent itself
    may do (`modules/agents/actor.py`); the check (`core/access.py`) applies it to
    whatever actor carries it, without knowing why. Without `drafts`, it sees pages
    as a viewer does (published only), whatever its role: a run whose answer is read
    by more than the person who asked (review M6 finding 1)."""

    roles: frozenset[tuple[uuid.UUID, SpaceRole]]
    drafts: bool = True

    @classmethod
    def of(cls, roles: Mapping[uuid.UUID, SpaceRole], *, drafts: bool = True) -> "ReadScope":
        return cls(frozenset(roles.items()), drafts)

    def cap(self, space_id: uuid.UUID) -> SpaceRole | None:
        return next((role for sid, role in self.roles if sid == space_id), None)

    def ids(self, min_role: SpaceRole = SpaceRole.VIEWER) -> list[uuid.UUID]:
        """The spaces where the scope allows at least `min_role`, sorted."""
        return sorted(sid for sid, role in self.roles if role >= min_role)


@dataclass(frozen=True, slots=True)
class WriteScope:
    """Where an actor may write at most (plan M6 decision 5): outside the spaces it
    lists, it may still read what its rights and its read scope allow, but no action
    that writes, posting in a channel included (`permissions.WRITE_ACTIONS`). An
    agent's run from a place in space S writes only in S (`modules/agents/scope.py`);
    the check applies it to whatever actor carries it."""

    space_ids: frozenset[uuid.UUID]

    @classmethod
    def of(cls, space_ids: Iterable[uuid.UUID]) -> "WriteScope":
        return cls(frozenset(space_ids))

    def allows(self, space_id: uuid.UUID) -> bool:
        return space_id in self.space_ids

    def ids(self) -> list[uuid.UUID]:
        return sorted(self.space_ids)


@dataclass(frozen=True, slots=True)
class Actor:
    """A snapshot taken by `actor_for` at the start of a request (or, later, of a
    tool call). The permission check re-reads the system role and whether the person
    is still active; group memberships come from `group_ids`, so an actor that should
    see a group change is built anew. `read_scope`, when set, narrows every check and
    every list filter (see `ReadScope`); `write_scope`, when set, every write (see
    `WriteScope`)."""

    org_id: uuid.UUID
    principal: Principal
    system_role: SystemRole
    group_ids: frozenset[uuid.UUID]
    read_scope: ReadScope | None = None
    write_scope: WriteScope | None = None

    @property
    def sees_drafts(self) -> bool:
        """Whether drafts may be shown at all (where `page.edit` is held)."""
        return self.read_scope is None or self.read_scope.drafts

    def writes_in(self, space_id: uuid.UUID) -> bool:
        return self.write_scope is None or self.write_scope.allows(space_id)

    @property
    def is_admin(self) -> bool:
        return self.system_role in ADMIN_ROLES

    @property
    def principals(self) -> list[Principal]:
        """Whoever's memberships count for this actor: itself and its groups."""
        return [self.principal, *(Principal.group(g) for g in sorted(self.group_ids))]
