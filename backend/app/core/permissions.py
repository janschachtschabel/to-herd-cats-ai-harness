"""The permission catalogue (spec 5.3). Values arrive with the milestone that needs them."""

from enum import StrEnum


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
