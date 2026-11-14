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
- `ticket_page_link`: a wiki page a ticket links (of any space, decision 11); it goes
  with either end (foreign keys), so purging a page removes its links.
- `work_item`: the ticket. Parent and child live in the same space, as do a ticket and
  its status: a database trigger refuses anything else. Tickets are never deleted on
  their own (cancelled is a status); they go with their space.
- `sprint` (plan M4b): a time box of a space. At most one sprint per space is active
  (a unique partial index); a ticket is in at most one sprint, always one of its own
  space (a foreign key over sprint and space). A closed sprint keeps its tally.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, Timestamps, UuidPk, utcnow
from app.core.principal import PrincipalType

KEY_PREFIX = "HC"  # a ticket's key is `HC-<number>` (plan M4 decision 1)
MAX_STATUSES = 20  # per space
MAX_STATUS_NAME_CHARS = 40
MAX_TITLE_CHARS = 200
MAX_DESCRIPTION_CHARS = 100_000
MAX_TAGS = 20  # per ticket
MAX_SPRINT_NAME_CHARS = 80
MAX_SPRINT_GOAL_CHARS = 500
# A sprint's dates lie in these years: finite (the driver sends date.min and date.max as
# -infinity and infinity, which the sprint list's order key cannot subtract).
FIRST_SPRINT_DAY = date(2000, 1, 1)
LAST_SPRINT_DAY = date(2100, 12, 31)
SPRINT_DATES_RANGE_SQL = (
    "isfinite(starts_on) AND isfinite(ends_on)"
    f" AND starts_on >= DATE '{FIRST_SPRINT_DAY.isoformat()}'"
    f" AND ends_on <= DATE '{LAST_SPRINT_DAY.isoformat()}'"
)


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


class SprintState(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    CLOSED = "closed"


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
        Index("ix_work_item_sprint_id", "sprint_id"),
        # A ticket's sprint is one of its own space (plan M4b decision 1).
        ForeignKeyConstraint(
            ["sprint_id", "space_id"],
            ["sprint.id", "sprint.space_id"],
            name="fk_work_item_sprint_id_sprint",
        ),
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
    # When the status last changed (or the ticket was made): set by the database
    # (trigger `work_item_status_changed_at`, migration m4b), whatever code writes.
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # The planned or active sprint it is in (or a closed one it was finished in);
    # none: the backlog.
    sprint_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    # Bumped by every change to the row; a write names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Read only by the list's text filter and the search; deferred.
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed(TICKET_TSV_SQL, persisted=True), deferred=True
    )


class TicketPageLink(OrgScoped, Base):
    """A wiki page the ticket links. Shown only to whoever sees both ends."""

    __tablename__ = "ticket_page_link"
    __table_args__ = (Index("ix_ticket_page_link_page_id", "page_id"),)

    work_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("work_item.id", ondelete="CASCADE"), primary_key=True
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("page.id", ondelete="CASCADE"), primary_key=True
    )
    # Orders a ticket's pages (last linked first).
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Sprint(UuidPk, OrgScoped, Base):
    """A time box of a space (plan M4b decision 2): planned, then active, then closed.
    Closing it records its tally (decision 3): the tickets it held, those done, those
    carried on to the next sprint or the backlog; null until then."""

    __tablename__ = "sprint"
    __table_args__ = (
        CheckConstraint(_in("state", SprintState), name="state"),
        CheckConstraint("ends_on >= starts_on", name="dates"),
        CheckConstraint(SPRINT_DATES_RANGE_SQL, name="dates_range"),
        CheckConstraint(
            f"char_length(name) BETWEEN 1 AND {MAX_SPRINT_NAME_CHARS}", name="name_length"
        ),
        CheckConstraint(f"char_length(goal) <= {MAX_SPRINT_GOAL_CHARS}", name="goal_length"),
        CheckConstraint(
            "(state = 'closed') = (planned_count IS NOT NULL)"
            " AND (planned_count IS NULL) = (done_count IS NULL)"
            " AND (planned_count IS NULL) = (carried_count IS NULL)",
            name="tally",
        ),
        UniqueConstraint("id", "space_id"),  # what a ticket's sprint refers to
        Index("ix_sprint_space_id_state", "space_id", "state"),
        Index(
            "uq_sprint_space_id_active",
            "space_id",
            unique=True,
            postgresql_where=text("state = 'active'"),
        ),
    )

    space_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(MAX_SPRINT_NAME_CHARS), nullable=False)
    goal: Mapped[str] = mapped_column(String(MAX_SPRINT_GOAL_CHARS), default="", nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[SprintState] = mapped_column(String(16), nullable=False)
    # Bumped by every change to the row; a write names the version it read (409).
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    planned_count: Mapped[int | None] = mapped_column(Integer)
    done_count: Mapped[int | None] = mapped_column(Integer)
    carried_count: Mapped[int | None] = mapped_column(Integer)
