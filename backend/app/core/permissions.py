"""The permission catalogue (spec 5.3) and which roles grant what. Values arrive with
the milestone that needs them. The rules are applied in one place: `app.core.access`."""

from enum import StrEnum

from app.core.principal import SystemRole


class Action(StrEnum):
    # Space-scoped
    SPACE_READ = "space.read"
    SPACE_MANAGE = "space.manage"
    PAGE_CREATE = "page.create"
    PAGE_EDIT = "page.edit"  # also: see drafts; publish one's own drafts
    PAGE_PUBLISH = "page.publish"  # publish anyone's drafts
    PAGE_TRASH = "page.trash"  # put into and take out of the trash
    PAGE_MODERATE = "page.moderate"  # also: the space's tags
    CHANNEL_POST = "channel.post"  # write and react in the space's channels and threads
    CHANNEL_MANAGE = "channel.manage"  # create, rename, archive channels; delete others' posts
    TICKET_READ = "ticket.read"  # see the space's tickets, their threads and statuses
    TICKET_CREATE = "ticket.create"
    TICKET_EDIT = "ticket.edit"  # also: assign oneself an unassigned ticket, or let go of it
    TICKET_ASSIGN = "ticket.assign"  # assign anyone who may read tickets in the space
    # System-wide
    SPACE_CREATE = "space.create"
    DIRECTORY_READ = "directory.read"  # find people and groups to add to a space
    USER_MANAGE = "user.manage"
    GROUP_MANAGE = "group.manage"
    AUDIT_READ = "audit.read"
    PAGE_PURGE = "page.purge"  # delete a trashed page for good (system admins)
    TAG_MANAGE = "tag.manage"  # system-wide tags (space tags: `page.moderate`)
    DM_INSPECT = "dm.inspect"  # read others' direct messages: audited, with a reason, 60 min


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
    Action.PAGE_CREATE: SpaceRole.EDITOR,
    Action.PAGE_EDIT: SpaceRole.EDITOR,
    Action.PAGE_PUBLISH: SpaceRole.MODERATOR,
    Action.PAGE_TRASH: SpaceRole.MODERATOR,
    Action.PAGE_MODERATE: SpaceRole.MODERATOR,
    Action.CHANNEL_POST: SpaceRole.VIEWER,
    Action.CHANNEL_MANAGE: SpaceRole.MODERATOR,
    Action.TICKET_READ: SpaceRole.VIEWER,
    Action.TICKET_CREATE: SpaceRole.EDITOR,
    Action.TICKET_EDIT: SpaceRole.EDITOR,
    Action.TICKET_ASSIGN: SpaceRole.MODERATOR,
}

# System roles that hold every right, in every space of their organisation (E4).
ADMIN_ROLES: frozenset[SystemRole] = frozenset({SystemRole.OWNER, SystemRole.ADMIN})

# System-wide actions per system role.
SYSTEM_ROLE_ACTIONS: dict[SystemRole, frozenset[Action]] = {
    SystemRole.OWNER: frozenset(Action),
    SystemRole.ADMIN: frozenset(Action),
    SystemRole.MEMBER: frozenset({Action.SPACE_CREATE, Action.DIRECTORY_READ}),
    SystemRole.GUEST: frozenset(),
}

# System roles that read every `open` space as `viewer` without a membership; guests
# see only spaces they are members of.
OPEN_SPACE_READERS: frozenset[SystemRole] = frozenset(
    {SystemRole.OWNER, SystemRole.ADMIN, SystemRole.MEMBER}
)
OPEN_SPACE_FLOOR = SpaceRole.VIEWER
