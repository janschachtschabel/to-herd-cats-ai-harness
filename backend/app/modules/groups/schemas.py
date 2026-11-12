import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.principal import PrincipalType
from app.modules.groups.repository import NamedGroupMember


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    version: int


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class GroupUpdate(BaseModel):
    """Fields left out stay as they are; an explicit null clears the description. Any
    other field is refused (422)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _name_is_not_cleared(cls, value: str | None) -> str:
        # Runs only for a name the client sent: null is not a name.
        if value is None:
            raise ValueError("name cannot be null")
        return value


class GroupUpdateIn(GroupUpdate):
    version: int


class GroupMemberIn(BaseModel):
    """People only in M1; agents join in M6."""

    member_type: Literal[PrincipalType.USER]
    member_id: uuid.UUID


class GroupMemberOut(BaseModel):
    """`name`: the person's display name."""

    member_type: PrincipalType
    member_id: uuid.UUID
    name: str

    @classmethod
    def of(cls, row: NamedGroupMember) -> "GroupMemberOut":
        return cls(
            member_type=row.member.member_type, member_id=row.member.member_id, name=row.name
        )
