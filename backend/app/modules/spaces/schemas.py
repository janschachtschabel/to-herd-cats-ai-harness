import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.permissions import SpaceRole
from app.core.principal import PrincipalType
from app.modules.ai.models import AiPolicy, DataLocation
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import NamedMember


class SpaceOut(BaseModel):
    """`my_role` is the caller's role there, for display (system admins: `admin`).
    `ai_policy`/`allowed_locations`: what AI may receive of the space (spec 7.3)."""

    id: uuid.UUID
    kind: SpaceKind
    name: str
    description: str | None
    icon: str | None
    owner_user_id: uuid.UUID | None
    version: int
    my_role: SpaceRole | None
    ai_policy: AiPolicy
    allowed_locations: list[DataLocation]

    @classmethod
    def of(cls, space: Space, my_role: SpaceRole | None) -> "SpaceOut":
        return cls(
            id=space.id,
            kind=space.kind,
            name=space.name,
            description=space.description,
            icon=space.icon,
            owner_user_id=space.owner_user_id,
            version=space.version,
            my_role=my_role,
            ai_policy=space.ai_policy,
            allowed_locations=[DataLocation(loc) for loc in space.allowed_locations],
        )


class SpaceCreate(BaseModel):
    """`personal` is a valid kind but not one the API creates (422 spaces.kind_not_allowed)."""

    kind: SpaceKind
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    icon: str | None = Field(default=None, max_length=32)


class SpaceUpdate(BaseModel):
    """Fields left out stay as they are; null clears description or icon. The kind of a
    space never changes, so it is not a field (sending it is 422). `allowed_locations`
    comes only with `ai_policy`: at least one for `restricted`, none otherwise (422)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    icon: str | None = Field(default=None, max_length=32)
    ai_policy: AiPolicy | None = None
    allowed_locations: list[DataLocation] | None = Field(default=None, max_length=3)

    @field_validator("name", "ai_policy")
    @classmethod
    def _not_cleared[T](cls, value: T | None) -> T:
        # Runs only for a value the client sent: null is not a name or a policy.
        if value is None:
            raise ValueError("cannot be null")
        return value

    @model_validator(mode="after")
    def _locations_fit_the_policy(self) -> "SpaceUpdate":
        if self.ai_policy is None:
            if "allowed_locations" in self.model_fields_set:
                raise ValueError("allowed_locations needs ai_policy")
            return self
        locations = sorted(set(self.allowed_locations or ()))
        if (self.ai_policy == AiPolicy.RESTRICTED) != bool(locations):
            raise ValueError("restricted needs allowed_locations, and only restricted has them")
        self.allowed_locations = locations
        return self


class SpaceUpdateIn(SpaceUpdate):
    version: int


MemberType = Literal[PrincipalType.USER, PrincipalType.GROUP, PrincipalType.AGENT]


class SpaceMemberIn(BaseModel):
    member_type: MemberType
    member_id: uuid.UUID
    role: SpaceRole


class SpaceMemberOut(BaseModel):
    """`name`: the person's, group's or agent's display name."""

    member_type: PrincipalType
    member_id: uuid.UUID
    role: SpaceRole
    name: str

    @classmethod
    def of(cls, row: NamedMember) -> "SpaceMemberOut":
        member = row.member
        return cls(
            member_type=member.member_type,
            member_id=member.member_id,
            role=member.role,
            name=row.name,
        )
