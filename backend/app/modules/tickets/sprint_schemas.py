import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.tickets.models import (
    MAX_SPRINT_GOAL_CHARS,
    MAX_SPRINT_NAME_CHARS,
    Sprint,
    SprintState,
)
from app.modules.tickets.sprints import MoveOpenTo

SprintName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_SPRINT_NAME_CHARS)
]
Goal = Annotated[str, Field(max_length=MAX_SPRINT_GOAL_CHARS, description="a short text")]


class SprintCreate(BaseModel):
    """A new sprint, planned; `ends_on` is no earlier than `starts_on`."""

    model_config = ConfigDict(extra="forbid")

    name: SprintName
    goal: Goal = ""
    starts_on: date
    ends_on: date


class SprintUpdate(BaseModel):
    """Fields left out stay as they are (none can be null); a closed sprint does not
    change (409 `sprint.state_invalid`)."""

    model_config = ConfigDict(extra="forbid")

    name: SprintName | None = None
    goal: Goal | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    version: int

    @field_validator("name", "goal", "starts_on", "ends_on")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:  # runs only for fields the client sent
            raise ValueError("cannot be null")
        return value


class SprintStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int


class SprintClose(BaseModel):
    """Where the sprint's unfinished tickets go: the space's next planned sprint (the
    one that starts first) or the backlog."""

    model_config = ConfigDict(extra="forbid")

    version: int
    move_open_to: MoveOpenTo


class SprintTally(BaseModel):
    """Recorded when the sprint closed: the tickets it held then, those done, and those
    carried on (to the next sprint or the backlog)."""

    planned: int
    done: int
    carried: int


class SprintOut(BaseModel):
    """`tally` only for a closed sprint. `version` guards writes (stale → 409)."""

    id: uuid.UUID
    space_id: uuid.UUID
    name: str
    goal: str
    starts_on: date
    ends_on: date
    state: SprintState
    tally: SprintTally | None
    version: int

    @classmethod
    def of(cls, sprint: Sprint) -> "SprintOut":
        tally = None
        if sprint.planned_count is not None:
            tally = SprintTally(
                planned=sprint.planned_count,
                done=sprint.done_count or 0,
                carried=sprint.carried_count or 0,
            )
        return cls(
            id=sprint.id,
            space_id=sprint.space_id,
            name=sprint.name,
            goal=sprint.goal,
            starts_on=sprint.starts_on,
            ends_on=sprint.ends_on,
            state=sprint.state,
            tally=tally,
            version=sprint.version,
        )
