import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.principal import PrincipalType
from app.modules.tags.schemas import TagOut
from app.modules.tickets.link_repository import LinkedPage
from app.modules.tickets.models import (
    MAX_DESCRIPTION_CHARS,
    MAX_TAGS,
    MAX_TITLE_CHARS,
    Priority,
    Sprint,
    SprintState,
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
    """A person, or (plan M6 decision 7) an agent: assigning an agent needs `ai.use`
    and `ticket.assign`, and starts its work on the ticket."""

    type: Literal[PrincipalType.USER, PrincipalType.AGENT]
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
    """Fields left out stay as they are; null clears `due_on`, `parent_id`, `assignee`
    and `sprint_id` (the others cannot be null). Taking an unassigned ticket or letting go
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
    sprint_id: uuid.UUID | None = Field(
        default=None, description="a planned or active sprint of the space; null: the backlog"
    )
    version: int

    @field_validator("title", "description_md", "kind", "status_id", "priority")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:  # runs only for fields the client sent
            raise ValueError("cannot be null")
        return value


class TicketTagsSet(BaseModel):
    """The ticket's tags from now on (the set replaces the old one): system-wide tags
    and tags of the ticket's space; `version` is the ticket version the client read."""

    model_config = ConfigDict(extra="forbid")

    tag_ids: list[uuid.UUID] = Field(max_length=MAX_TAGS)
    version: int


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
    number. `version` guards writes (send it back; stale → 409). `tags` by name.
    `status_changed_at`: when its status last changed (or it was made)."""

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
    sprint_id: uuid.UUID | None
    tags: list[TagOut]
    version: int
    created_at: datetime
    updated_at: datetime
    status_changed_at: datetime

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
            "sprint_id": t.sprint_id,
            "tags": [TagOut.of(tag) for tag in view.tags],
            "version": t.version,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
            "status_changed_at": t.status_changed_at,
        }

    @classmethod
    def of(cls, view: TicketView) -> "TicketSummaryOut":
        return cls.model_validate(cls.fields_of(view))


class TicketSprintOut(BaseModel):
    """The ticket's sprint (one of its own space)."""

    id: uuid.UUID
    name: str
    state: SprintState


class TicketOut(TicketSummaryOut):
    """A ticket with its description, how many children it has per category and its
    sprint by name (module review M4b, finding 10)."""

    description_md: str
    children: ChildCounts
    sprint: TicketSprintOut | None

    @classmethod
    def full(
        cls, view: TicketView, children: dict[StatusCategory, int], sprint: Sprint | None
    ) -> "TicketOut":
        counts = ChildCounts(**{c.value: children.get(c, 0) for c in StatusCategory})
        shown = None
        if sprint is not None:
            shown = TicketSprintOut(id=sprint.id, name=sprint.name, state=sprint.state)
        return cls.model_validate(
            {
                **cls.fields_of(view),
                "description_md": view.ticket.description_md,
                "children": counts,
                "sprint": shown,
            }
        )


class LinkedPageOut(BaseModel):
    """A page the ticket links (one the caller sees)."""

    id: uuid.UUID
    space_id: uuid.UUID
    space_name: str
    title: str
    path: str
    linked_at: datetime

    @classmethod
    def of(cls, page: LinkedPage) -> "LinkedPageOut":
        return cls(
            id=page.page_id,
            space_id=page.space_id,
            space_name=page.space_name,
            title=page.title,
            path=page.path,
            linked_at=page.linked_at,
        )
