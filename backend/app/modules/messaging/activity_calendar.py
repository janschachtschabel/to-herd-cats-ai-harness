"""Notifications about calendar events in the activity view (plan M10 task 4).

`calendars` builds on messaging, so its tables are named here, not imported (as with
proposals and automations). A notification bound to an event (`calendar_event_id`) is
seen while the person attends that event row: organises it or has an attendee row on
it (a tombstone too, which tells her it was deleted), in a calendar that is not
archived. Attending means seeing the event in full (`calendars/sight.py`), so the
entry may name its title, times and her own answer; whoever no longer attends sees
nothing of it, a reader of a private event's calendar included.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ColumnElement,
    DateTime,
    String,
    Uuid,
    and_,
    column,
    exists,
    or_,
    select,
    table,
)

from app.modules.messaging.notification_models import Notification

EVENT = table(
    "calendar_event",
    column("id", Uuid),
    column("calendar_id", Uuid),
    column("title", String),
    column("starts_at", DateTime(timezone=True)),
    column("ends_at", DateTime(timezone=True)),
    column("all_day", Boolean),
    column("status", String),
    column("deleted_at", DateTime(timezone=True)),
    column("organizer_type", String),
    column("organizer_id", Uuid),
)
ATTENDEE = table(
    "calendar_event_attendee",
    column("event_id", Uuid),
    column("principal_type", String),
    column("principal_id", Uuid),
    column("response", String),
)
CALENDAR = table("calendar", column("id", Uuid), column("archived_at", DateTime(timezone=True)))


@dataclass(frozen=True, slots=True)
class EventEntry:
    """What an entry shows of its event: `cancelled` when it was called off or
    deleted; `response` the person's own answer (none: she organises it)."""

    id: uuid.UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    cancelled: bool
    response: str | None


def _mine(person: uuid.UUID) -> ColumnElement[bool]:
    return and_(ATTENDEE.c.principal_type == "user", ATTENDEE.c.principal_id == person)


def seen(person: uuid.UUID) -> ColumnElement[bool]:
    """Whether the notification's event is one the person attends now."""
    shown = EVENT.alias("seen_calendar_event")
    calendar = CALENDAR.alias("seen_calendar")
    invited = (
        select(ATTENDEE.c.event_id)
        .where(ATTENDEE.c.event_id == shown.c.id, _mine(person))
        .correlate(shown)
        .exists()
    )
    attends = (
        exists()
        .where(
            shown.c.id == Notification.calendar_event_id,
            calendar.c.id == shown.c.calendar_id,
            calendar.c.archived_at.is_(None),
            or_(and_(shown.c.organizer_type == "user", shown.c.organizer_id == person), invited),
        )
        .correlate_except(shown, calendar)
    )
    return and_(Notification.calendar_event_id.is_not(None), attends)


def columns(person: uuid.UUID) -> list[ColumnElement[object]]:
    """The event's columns for the entry (the list joins `EVENT` on the notification),
    the person's own answer last."""
    answer = (
        select(ATTENDEE.c.response)
        .where(ATTENDEE.c.event_id == EVENT.c.id, _mine(person))
        .scalar_subquery()
    )
    cancelled = or_(EVENT.c.status == "cancelled", EVENT.c.deleted_at.is_not(None))
    return [
        EVENT.c.id,
        EVENT.c.title,
        EVENT.c.starts_at,
        EVENT.c.ends_at,
        EVENT.c.all_day,
        cancelled,
        answer,
    ]


def entry(values: Sequence[object]) -> EventEntry | None:
    """The event of a row's `columns` (none for a notification of another kind)."""
    event_id, title, starts_at, ends_at, all_day, cancelled, response = values
    if not isinstance(event_id, uuid.UUID):
        return None
    assert isinstance(title, str) and isinstance(starts_at, datetime)
    assert isinstance(ends_at, datetime)
    return EventEntry(
        event_id,
        title,
        starts_at,
        ends_at,
        bool(all_day),
        bool(cancelled),
        response if isinstance(response, str) else None,
    )
