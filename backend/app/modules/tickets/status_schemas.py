import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.tickets.models import (
    MAX_STATUS_NAME_CHARS,
    MAX_STATUSES,
    StatusCategory,
    TicketStatus,
)

# One line, as on a board column's head.
StatusName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_STATUS_NAME_CHARS,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
Position = Annotated[int, Field(ge=0, le=MAX_STATUSES - 1)]


class StatusOut(BaseModel):
    """A status of a space's workflow; `position` orders a space's statuses (0 first);
    the logic reads only `category`."""

    id: uuid.UUID
    space_id: uuid.UUID
    name: str
    position: int
    category: StatusCategory
    version: int

    @classmethod
    def of(cls, status: TicketStatus) -> "StatusOut":
        return cls(
            id=status.id,
            space_id=status.space_id,
            name=status.name,
            position=status.position,
            category=status.category,
            version=status.version,
        )


class StatusCreate(BaseModel):
    """Without `position`, the new status comes last."""

    name: StatusName
    category: StatusCategory
    position: Position | None = None


class StatusUpdate(BaseModel):
    """Fields left out stay as they are; none of them can be null. `position` moves
    the status there, the others close up."""

    model_config = ConfigDict(extra="forbid")

    name: StatusName | None = None
    category: StatusCategory | None = None
    position: Position | None = None
    version: int

    @field_validator("name", "category", "position")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:  # runs only for fields the client sent
            raise ValueError("cannot be null")
        return value
