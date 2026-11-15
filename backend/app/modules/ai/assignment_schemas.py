"""AI assignments as the API takes and shows them (admins only)."""

import uuid
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.ai.assignment_repository import Named
from app.modules.ai.models import GroupAssignment, UserAssignment
from app.modules.ai.schemas import ModelName

MAX_GROUP_ASSIGNMENTS = 100


class TargetIn(BaseModel):
    """A chat connection and one of its models (route names for the b-api)."""

    model_config = ConfigDict(extra="forbid")

    connection_id: uuid.UUID
    model: ModelName


class TargetOut(BaseModel):
    connection_id: uuid.UUID
    connection_name: str
    model: str


class DefaultIn(BaseModel):
    """`target: null`: no standard, so only people and groups with an assignment have AI."""

    model_config = ConfigDict(extra="forbid")

    target: TargetIn | None
    version: int


class AssignmentsOut(BaseModel):
    """The standard assignment and whether people with `ai.use` may create personal
    agents; `version` guards both and the group list."""

    default: TargetOut | None
    personal_agents: bool
    version: int


class PersonalAgentsIn(BaseModel):
    """Allow (or stop) personal agents for everyone with `ai.use`; off, existing
    personal agents stop working (`agent.personal_disabled`)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    version: int


class GroupItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: uuid.UUID
    connection_id: uuid.UUID
    model: ModelName


class GroupsIn(BaseModel):
    """The whole ordered list; for a person in several groups the first one wins."""

    model_config = ConfigDict(extra="forbid")

    items: list[GroupItemIn] = Field(max_length=MAX_GROUP_ASSIGNMENTS)
    version: int


class GroupAssignmentOut(BaseModel):
    group_id: uuid.UUID
    group_name: str
    position: int
    target: TargetOut

    @classmethod
    def of(cls, named: Named[GroupAssignment]) -> "GroupAssignmentOut":
        row = named.row
        target = TargetOut(
            connection_id=row.connection_id,
            connection_name=named.connection_name or "",
            model=row.model,
        )
        return cls(
            group_id=row.group_id, group_name=named.name, position=row.position, target=target
        )


class UserAssignmentIn(BaseModel):
    """A connection and model, or `no_ai: true`. `version`: the one read, or null to
    create (409 if the person has one meanwhile)."""

    model_config = ConfigDict(extra="forbid")

    no_ai: bool = False
    target: TargetIn | None = None
    version: int | None

    @model_validator(mode="after")
    def _either(self) -> Self:
        if self.no_ai == (self.target is not None):
            raise ValueError("give a target or no_ai: true")
        return self


class UserAssignmentOut(BaseModel):
    user_id: uuid.UUID
    user_name: str
    no_ai: bool
    target: TargetOut | None
    version: int

    @classmethod
    def of(cls, named: Named[UserAssignment]) -> "UserAssignmentOut":
        row = named.row
        target = None
        if row.connection_id is not None and row.model is not None:
            target = TargetOut(
                connection_id=row.connection_id,
                connection_name=named.connection_name or "",
                model=row.model,
            )
        return cls(
            user_id=row.user_id,
            user_name=named.name,
            no_ai=row.no_ai,
            target=target,
            version=row.version,
        )
