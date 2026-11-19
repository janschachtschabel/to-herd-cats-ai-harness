"""Calendars (plan M10 decision 2): every calendar belongs to one space, whose rights
are its rights; the organisation's calendar switches."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk

MAX_CALENDARS_PER_SPACE = 20
NAME_MAX = 120
# A calendar's zone unless one is named (plan M10 task 3a ruling: the interface's
# default language is German).
DEFAULT_TIME_ZONE = "Europe/Berlin"
TIME_ZONE_MAX = 64


class CalendarColor(StrEnum):
    """The eight fixed tones a calendar is drawn in (plan M10 decision 17)."""

    BLUE = "blue"
    GREEN = "green"
    AMBER = "amber"
    RED = "red"
    VIOLET = "violet"
    TEAL = "teal"
    PINK = "pink"
    SLATE = "slate"


_COLORS = ", ".join(f"'{c.value}'" for c in CalendarColor)


class Calendar(UuidPk, OrgScoped, Base):
    """A calendar of a space: a personal space's is a personal calendar, a team space's
    a team calendar, an open space's the organisation's. At most
    `MAX_CALENDARS_PER_SPACE` that are not archived per space (`service.create`, under
    the space's row lock); at most one default per space (`defaults.py`, the partial
    unique index). An archived calendar is gone for everyone (404); a default one is
    never archived. A default calendar has no `name` until someone renames it: the
    interface names it in the reader's language („Mein Kalender“, „Allgemein“)."""

    __tablename__ = "calendar"
    __table_args__ = (
        CheckConstraint(f"color IN ({_COLORS})", name="color"),
        CheckConstraint("name IS NOT NULL OR is_default", name="name"),
        UniqueConstraint("id", "space_id"),  # what an event's calendar refers to
        Index("ix_calendar_space_id", "space_id"),
        Index(
            "uq_calendar_space_id_default",
            "space_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    space_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("space.id", ondelete="CASCADE"), nullable=False
    )
    # Null only for a default calendar nobody renamed (the interface words it).
    name: Mapped[str | None] = mapped_column(String(NAME_MAX))
    color: Mapped[CalendarColor] = mapped_column(String(16), nullable=False)
    # Made by the system on the first call (`defaults.py`), never by a person.
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # IANA name: the zone of a new event that names none (`events.EventService.create`).
    time_zone: Mapped[str] = mapped_column(
        String(TIME_ZONE_MAX),
        nullable=False,
        default=DEFAULT_TIME_ZONE,
        server_default=DEFAULT_TIME_ZONE,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class CalendarSetting(Base):
    """The organisation's calendar switches, set with `calendar.manage` (audited):
    `sync_enabled` gives `calendar.sync` to every active person but guests (decision
    2; off by default, because data leaves the house). Without a row: off."""

    __tablename__ = "calendar_setting"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), primary_key=True
    )
    sync_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
