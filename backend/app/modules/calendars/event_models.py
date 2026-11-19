"""Events (plan M10 decision 5). The table is `calendar_event` (apart from `run_event`,
`event_outbox` and `automation_event`); outbox types are `calendar_event.*`, API codes
`event.*`.

- An event belongs to a calendar and, through it, to its space: the foreign key
  `(calendar_id, space_id)` lets lists filter by space in SQL.
- Times: `starts_at`/`ends_at` are instants; an all-day event floats on 00:00 UTC of
  its first day and of the day after its last, without a zone. Any other event has an
  IANA zone (`tzid`), in whose wall time its series is expanded.
- A series stores its rule, never its occurrences: `rrule`, `rdates` and `exdates`
  (wall times in `tzid`, all-day: 00:00 of the day), expanded when read
  (`recurrence.occurrences`). `recurs_until` is when the last occurrence ends (a
  single event: its end; NULL: endless), so a window loads only what can reach it.
- An override (`series_id`, `recurrence_id`: the wall time of the occurrence it takes
  the place of) is a row of its own with the series' UID.
- `deleted_at`: a tombstone (task 3b), seen by nobody, blocking no UID.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk
from app.core.principal import PrincipalType

UID_MAX = 500
TITLE_MAX = 300
LOCATION_MAX = 500
DESCRIPTION_MAX = 20_000
RRULE_MAX = 500
DATES_MAX = 500  # RDATEs, and EXDATEs, per series
TZID_MAX = 64


class EventStatus(StrEnum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class EventVisibility(StrEnum):
    """`private`: only the organiser (and, on the named way, admins) sees its content;
    every other reader of the calendar sees times and "busy" (`sight.py`)."""

    DEFAULT = "default"
    PRIVATE = "private"


def _values(kind: type[StrEnum]) -> str:
    return ", ".join(f"'{v.value}'" for v in kind)


class CalendarEvent(UuidPk, OrgScoped, Base):
    __tablename__ = "calendar_event"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(EventStatus)})", name="status"),
        CheckConstraint(f"visibility IN ({_values(EventVisibility)})", name="visibility"),
        CheckConstraint("organizer_type IN ('user', 'agent')", name="organizer_type"),
        CheckConstraint("ends_at >= starts_at", name="times"),
        CheckConstraint("all_day = (tzid IS NULL)", name="zone"),
        CheckConstraint("(series_id IS NULL) = (recurrence_id IS NULL)", name="override"),
        ForeignKeyConstraint(
            ["calendar_id", "space_id"],
            ["calendar.id", "calendar.space_id"],
            name="fk_calendar_event_calendar_id_calendar",
            ondelete="CASCADE",
        ),
        # One master per UID and calendar, one override per occurrence; a tombstone
        # blocks nothing (decision 5, I3).
        Index(
            "uq_calendar_event_uid",
            "calendar_id",
            "uid",
            "recurrence_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            postgresql_nulls_not_distinct=True,
        ),
        Index(
            "ix_calendar_event_window",
            "calendar_id",
            "starts_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_calendar_event_organizer",
            "organizer_id",
            "starts_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_calendar_event_series_id", "series_id"),
        Index("ix_calendar_event_space_id", "space_id"),
    )

    calendar_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    space_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    uid: Mapped[str] = mapped_column(String(UID_MAX), nullable=False)
    title: Mapped[str] = mapped_column(String(TITLE_MAX), nullable=False)
    # Plain text, never rendered as HTML or Markdown.
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    location: Mapped[str] = mapped_column(
        String(LOCATION_MAX), nullable=False, default="", server_default=""
    )
    all_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tzid: Mapped[str | None] = mapped_column(String(TZID_MAX))
    rrule: Mapped[str | None] = mapped_column(String(RRULE_MAX))
    rdates: Mapped[list[datetime]] = mapped_column(
        ARRAY(DateTime(timezone=False)), nullable=False, default=list, server_default="{}"
    )
    exdates: Mapped[list[datetime]] = mapped_column(
        ARRAY(DateTime(timezone=False)), nullable=False, default=list, server_default="{}"
    )
    recurs_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("calendar_event.id", ondelete="CASCADE")
    )
    recurrence_id: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    status: Mapped[EventStatus] = mapped_column(
        String(16), nullable=False, default=EventStatus.CONFIRMED
    )
    visibility: Mapped[EventVisibility] = mapped_column(
        String(16), nullable=False, default=EventVisibility.DEFAULT
    )
    busy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    organizer_type: Mapped[PrincipalType] = mapped_column(String(16), nullable=False)
    organizer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def recurring(self) -> bool:
        """A series (a rule or extra dates), expanded when read."""
        return self.rrule is not None or bool(self.rdates)
