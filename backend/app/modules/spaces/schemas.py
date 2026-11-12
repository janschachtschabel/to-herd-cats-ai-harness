import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.permissions import SpaceRole
from app.core.principal import PrincipalType
from app.modules.spaces.models import SpaceKind


class SpaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: SpaceKind
    name: str
    slug: str
    description: str | None
    icon: str | None
    owner_user_id: uuid.UUID | None
    version: int


class SpaceCreate(BaseModel):
    """`personal` is a valid kind but not one the API creates (422 spaces.kind_not_allowed)."""

    kind: SpaceKind
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    icon: str | None = Field(default=None, max_length=32)


class SpaceUpdate(BaseModel):
    """Fields left out stay as they are; null clears description or icon. The kind of a
    space never changes, so it is not a field (sending it is 422)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    icon: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def _name_is_not_cleared(cls, value: str | None) -> str:
        # Runs only for a name the client sent: null is not a name.
        if value is None:
            raise ValueError("name cannot be null")
        return value


class SpaceUpdateIn(SpaceUpdate):
    version: int


MemberType = Literal[PrincipalType.USER, PrincipalType.GROUP]


class SpaceMemberIn(BaseModel):
    member_type: MemberType
    member_id: uuid.UUID
    role: SpaceRole


class SpaceMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_type: PrincipalType
    member_id: uuid.UUID
    role: SpaceRole
