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
