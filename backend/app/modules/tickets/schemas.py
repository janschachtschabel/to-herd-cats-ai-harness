import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.principal import PrincipalType
from app.modules.tickets.models import (
    MAX_DESCRIPTION_CHARS,
    MAX_TITLE_CHARS,
    Priority,
    StatusCategory,
    TicketKind,
    ticket_key,
)
from app.modules.tickets.repository import TicketView

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_CHARS)
]
Description = Annotated[str, Field(max_length=MAX_DESCRIPTION_CHARS, description="Markdown")]


class AssigneeIn(BaseModel):
    """M4 assigns people only."""

    type: Literal[PrincipalType.USER]
    id: uuid.UUID


class TicketCreate(BaseModel):
    """Without `status_id`, the space's first status of category `open`. An assignee
    other than oneself needs `ticket.assign`."""

    model_config = ConfigDict(extra="forbid")

    title: Title
    description_md: Description = ""
    kind: TicketKind = TicketKind.TASK
    status_id: uuid.UUID | None = None
    priority: Priority = Priority.NORMAL
    due_on: date | None = None
    parent_id: uuid.UUID | None = None
    assignee: AssigneeIn | None = None


class TicketUpdate(BaseModel):
    """Fields left out stay as they are; null clears `due_on`, `parent_id` and
    `assignee` (the others cannot be null). Taking an unassigned ticket or letting go
    of one's own needs `ticket.edit`; any other assignment `ticket.assign`."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description_md: Description | None = None
    kind: TicketKind | None = None
    status_id: uuid.UUID | None = None
    priority: Priority | None = None
    due_on: date | None = None
    parent_id: uuid.UUID | None = None
    assignee: AssigneeIn | None = None
    version: int

    @field_validator("title", "description_md", "kind", "status_id", "priority")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:  # runs only for fields the client sent
            raise ValueError("cannot be null")
        return value


class StatusRef(BaseModel):
    id: uuid.UUID
    name: str
    category: StatusCategory


class PersonOut(BaseModel):
    """`name` is null only for someone the organisation does not know (any more)."""

    type: PrincipalType
    id: uuid.UUID
    name: str | None


class ParentOut(BaseModel):
    id: uuid.UUID
    number: int
    key: str
    title: str
    kind: TicketKind


class ChildCounts(BaseModel):
    """How many children the ticket has, per status category."""

    open: int
    active: int
    review: int
    done: int
    cancelled: int


class TicketSummaryOut(BaseModel):
    """A ticket as a list row shows it. `key` is `HC-<number>`; addresses use the
    number. `version` guards writes (send it back; stale → 409)."""

    id: uuid.UUID
    number: int
    key: str
    space_id: uuid.UUID
    kind: TicketKind
    title: str
    status: StatusRef
    priority: Priority
    assignee: PersonOut | None
    reporter: PersonOut
    due_on: date | None
    parent: ParentOut | None
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def fields_of(cls, view: TicketView) -> dict[str, object]:
        t = view.ticket
        assignee = None
        if t.assignee_type is not None and t.assignee_id is not None:
            assignee = PersonOut(type=t.assignee_type, id=t.assignee_id, name=view.assignee_name)
        parent = None
        if view.parent is not None:
            p = view.parent
            parent = ParentOut(
                id=p.id, number=p.number, key=ticket_key(p.number), title=p.title, kind=p.kind
            )
        return {
            "id": t.id,
            "number": t.number,
            "key": ticket_key(t.number),
            "space_id": t.space_id,
            "kind": t.kind,
            "title": t.title,
            "status": StatusRef(
                id=view.status.id, name=view.status.name, category=view.status.category
            ),
            "priority": t.priority,
            "assignee": assignee,
            "reporter": PersonOut(type=t.reporter_type, id=t.reporter_id, name=view.reporter_name),
            "due_on": t.due_on,
            "parent": parent,
            "version": t.version,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }

    @classmethod
    def of(cls, view: TicketView) -> "TicketSummaryOut":
        return cls.model_validate(cls.fields_of(view))


class TicketOut(TicketSummaryOut):
    """A ticket with its description and how many children it has per category."""

    description_md: str
    children: ChildCounts

    @classmethod
    def full(cls, view: TicketView, children: dict[StatusCategory, int]) -> "TicketOut":
        counts = ChildCounts(**{c.value: children.get(c, 0) for c in StatusCategory})
        return cls.model_validate(
            {
                **cls.fields_of(view),
                "description_md": view.ticket.description_md,
                "children": counts,
            }
        )
