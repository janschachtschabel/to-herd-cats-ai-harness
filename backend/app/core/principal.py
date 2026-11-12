"""Who acts and in which system role.

A principal is whoever can act or be granted something: a person, an AI agent (M6)
or a group. Authorship and memberships store `(type, id)`; ACL logic never
special-cases agents.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum


class PrincipalType(StrEnum):
    USER = "user"
    AGENT = "agent"
    GROUP = "group"


class SystemRole(StrEnum):
    """A person's organisation-wide role. There is always at least one active owner."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    GUEST = "guest"


@dataclass(frozen=True, slots=True)
class Principal:
    type: PrincipalType
    id: uuid.UUID

    @classmethod
    def user(cls, user_id: uuid.UUID) -> "Principal":
        return cls(PrincipalType.USER, user_id)

    @classmethod
    def group(cls, group_id: uuid.UUID) -> "Principal":
        return cls(PrincipalType.GROUP, group_id)

    def __str__(self) -> str:
        """`user:<id>`: the form of the `actor` log field."""
        return f"{self.type}:{self.id}"
