"""The permission catalogue (spec 5.3) and which roles grant what. Values arrive with
the milestone that needs them. The rules are applied in one place: `app.core.access`."""

from enum import StrEnum

from app.core.principal import SystemRole


class Action(StrEnum):
    # Space-scoped
    SPACE_READ = "space.read"
    SPACE_MANAGE = "space.manage"
    # System-wide
    SPACE_CREATE = "space.create"
    USER_MANAGE = "user.manage"
    GROUP_MANAGE = "group.manage"
    AUDIT_READ = "audit.read"


class SpaceRole(StrEnum):
    """A role inside one space, ordered `viewer < editor < moderator < admin` (by rank,
    not alphabetically, so `max()` gives the strongest)."""

    VIEWER = "viewer"
    EDITOR = "editor"
    MODERATOR = "moderator"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        return list(SpaceRole).index(self)

    @classmethod
    def from_rank(cls, rank: int) -> "SpaceRole":
        return list(cls)[rank]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SpaceRole):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, SpaceRole):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SpaceRole):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, SpaceRole):
            return NotImplemented
        return self.rank >= other.rank


# The lowest space role each space-scoped action needs.
SPACE_ACTION_MIN_ROLE: dict[Action, SpaceRole] = {
    Action.SPACE_READ: SpaceRole.VIEWER,
    Action.SPACE_MANAGE: SpaceRole.ADMIN,
}

# System roles that hold every right, in every space of their organisation (E4).
ADMIN_ROLES: frozenset[SystemRole] = frozenset({SystemRole.OWNER, SystemRole.ADMIN})

# System-wide actions per system role.
SYSTEM_ROLE_ACTIONS: dict[SystemRole, frozenset[Action]] = {
    SystemRole.OWNER: frozenset(Action),
    SystemRole.ADMIN: frozenset(Action),
    SystemRole.MEMBER: frozenset({Action.SPACE_CREATE}),
    SystemRole.GUEST: frozenset(),
}

# System roles that read every `open` space as `viewer` without a membership; guests
# see only spaces they are members of.
OPEN_SPACE_READERS: frozenset[SystemRole] = frozenset(
    {SystemRole.OWNER, SystemRole.ADMIN, SystemRole.MEMBER}
)
OPEN_SPACE_FLOOR = SpaceRole.VIEWER
