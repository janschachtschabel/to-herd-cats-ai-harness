import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.core.pagination import PageParams
from app.core.principal import PrincipalType
from app.modules.directory.repository import DirectoryEntry


class DirectoryQuery(PageParams):
    """`q`: part of a person's, group's or agent's name (never the email); empty lists
    everyone (agents only for those with `ai.use`).
    `space_id`: only the people (never groups) who may read that space and the agents
    that are its members, for pickers of assignees and mentions; a space the caller
    cannot read is 404."""

    q: str = Field(default="", max_length=100)
    type: Literal[PrincipalType.USER, PrincipalType.GROUP, PrincipalType.AGENT] | None = None
    space_id: uuid.UUID | None = Field(
        default=None, description="only people who read this space, and its member agents"
    )


class DirectoryEntryOut(BaseModel):
    """Who can be added to a space or written to. Deliberately no email or role: any
    member may read it."""

    type: Literal[PrincipalType.USER, PrincipalType.GROUP, PrincipalType.AGENT]
    id: uuid.UUID
    name: str

    @classmethod
    def of(cls, entry: DirectoryEntry) -> "DirectoryEntryOut":
        return cls(type=entry.type, id=entry.id, name=entry.name)
