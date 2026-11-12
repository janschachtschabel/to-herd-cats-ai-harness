import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.core.pagination import PageParams
from app.core.principal import PrincipalType
from app.modules.directory.repository import DirectoryEntry


class DirectoryQuery(PageParams):
    """`q`: part of a person's or group's name (never the email); empty lists everyone."""

    q: str = Field(default="", max_length=100)
    type: Literal[PrincipalType.USER, PrincipalType.GROUP] | None = None


class DirectoryEntryOut(BaseModel):
    """Who can be added to a space. Deliberately no email or role: any member may read it."""

    type: Literal[PrincipalType.USER, PrincipalType.GROUP]
    id: uuid.UUID
    name: str

    @classmethod
    def of(cls, entry: DirectoryEntry) -> "DirectoryEntryOut":
        return cls(type=entry.type, id=entry.id, name=entry.name)
