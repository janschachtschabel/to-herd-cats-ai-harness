"""Tickets (spec 10): work items per space, numbered per organisation, with a status
workflow per space.

- `ticket_status`: a space's statuses (name, position, category). The logic reads only
  the category; names are data. Every space gets five statuses when it is created (a
  database trigger, migration m4 tickets, so spaces created by any code path, the
  previous release's included, have them); a space always keeps one of category
  `open` and one of category `done` (`statuses.py`). Names are unique in a space,
  ignoring case.
- `ticket_counter`: the last number given out per organisation; a new ticket takes
  the next one in its own transaction (`UPDATE … RETURNING`), so numbers never repeat.
- `work_item`: the ticket. Parent and child live in the same space, as do a ticket and
  its status: a database trigger refuses anything else. Tickets are never deleted on
  their own (cancelled is a status); they go with their space.
"""

import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk
from app.core.principal import PrincipalType

KEY_PREFIX = "HC"  # a ticket's key is `HC-<number>` (plan M4 decision 1)
MAX_STATUSES = 20  # per space
MAX_STATUS_NAME_CHARS = 40
MAX_TITLE_CHARS = 200
MAX_DESCRIPTION_CHARS = 100_000


def ticket_key(number: int) -> str:
    return f"{KEY_PREFIX}-{number}"


class StatusCategory(StrEnum):
    OPEN = "open"
    ACTIVE = "active"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"


# Every space must keep at least one status of each of these categories.
REQUIRED_CATEGORIES = (StatusCategory.OPEN, StatusCategory.DONE)


class TicketKind(StrEnum):
    EPIC = "epic"
    STORY = "story"
    TASK = "task"
    BUG = "bug"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

    @property
    def rank(self) -> int:
        return list(Priority).index(self)


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class TicketStatus(UuidPk, OrgScoped, Base):
    __tablename__ = "ticket_status"
    __table_args__ = (
        CheckConstraint(_in("category", StatusCategory), name="category"),
        CheckConstraint(
            f"char_length(name) BETWEEN 1 AND {MAX_STATUS_NAME_CHARS}", name="name_length"
        ),
        Index("ix_ticket_status_space_id_position", "space_id", "position"),
    )

    space_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(MAX_STATUS_NAME_CHARS), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[StatusCategory] = mapped_column(String(16), nullable=False)
    # Bumped by every change to the row; a write names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


# A status's name, unique in its space without regard to case.
Index(
    "uq_ticket_status_space_id_name",
    TicketStatus.space_id,
    func.lower(TicketStatus.name).label("name_lower"),
    unique=True,
)


class TicketCounter(Base):
    """The last ticket number given out in the organisation."""

    __tablename__ = "ticket_counter"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), primary_key=True
    )
    last_number: Mapped[int] = mapped_column(Integer, nullable=False)


# Full-text search: like a page (title stemmed and as written, then the description).
TICKET_TSV_SQL = (
    "setweight(to_tsvector('german'::regconfig, title), 'A') || "
    "setweight(to_tsvector('simple'::regconfig, title), 'A') || "
    "setweight(to_tsvector('german'::regconfig, description_md), 'B')"
)


class WorkItem(UuidPk, OrgScoped, Timestamps, Base):
    __tablename__ = "work_item"
    __table_args__ = (
        UniqueConstraint("org_id", "number"),
        CheckConstraint(_in("kind", TicketKind), name="kind"),
        CheckConstraint(_in("priority", Priority), name="priority"),
        CheckConstraint(f"char_length(title) BETWEEN 1 AND {MAX_TITLE_CHARS}", name="title_length"),
        CheckConstraint(
            f"char_length(description_md) <= {MAX_DESCRIPTION_CHARS}", name="description_length"
        ),
        # M4: people only; agents widen these checks in M6.
        CheckConstraint(
            "(assignee_type IS NULL) = (assignee_id IS NULL)"
            " AND (assignee_type IS NULL OR assignee_type IN ('user'))",
            name="assignee",
        ),
        CheckConstraint("reporter_type IN ('user')", name="reporter_type"),
        CheckConstraint("parent_id <> id", name="parent_not_self"),
        Index("ix_work_item_space_id_status_id", "space_id", "status_id"),
        Index("ix_work_item_assignee", "assignee_type", "assignee_id"),
        Index("ix_work_item_parent_id", "parent_id"),
        Index("ix_work_item_search_tsv", "search_tsv", postgresql_using="gin"),
    )

    space_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[TicketKind] = mapped_column(String(16), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("work_item.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(MAX_TITLE_CHARS), nullable=False)
    description_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ticket_status.id"), nullable=False
    )
    priority: Mapped[Priority] = mapped_column(String(16), nullable=False)
    assignee_type: Mapped[PrincipalType | None] = mapped_column(String(16))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    reporter_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    reporter_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # A day without time or zone (plan M4 decision 7).
    due_on: Mapped[date | None] = mapped_column(Date)
    # Bumped by every change to the row; a write names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Read only by the list's text filter and the search; deferred.
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed(TICKET_TSV_SQL, persisted=True), deferred=True
    )
