"""An event as iCalendar carries it (plan M10 decisions 5 and 10): what reading gives
and what writing takes. Pure data; times are `recurrence.Series` (wall times in the
series' zone, all-day on midnights), so a draft expands like a stored event.

The values follow decision 5 (`status`, `visibility`, `busy`) and 7 (an attendee's
role and response); the limits are decision 5's (title, place, text, 100 attendees)
and 8's (three reminders, at most four weeks before).
"""

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Self

from app.modules.calendars.recurrence import Series

MAX_UID = 500
MAX_TITLE = 300
MAX_LOCATION = 500
MAX_DESCRIPTION = 20_000
MAX_ATTENDEES = 100
MAX_ALARMS = 3
MAX_ALARM_MINUTES = 40_320  # four weeks


class Status(StrEnum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class Visibility(StrEnum):
    DEFAULT = "default"
    PRIVATE = "private"


class Role(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class Response(StrEnum):
    NEEDS_ACTION = "needs_action"
    ACCEPTED = "accepted"
    TENTATIVE = "tentative"
    DECLINED = "declined"


@dataclass(frozen=True, slots=True)
class AttendeeDraft:
    email: str  # the address as written, without "mailto:"
    name: str | None = None
    role: Role = Role.REQUIRED
    response: Response = Response.NEEDS_ACTION


@dataclass(frozen=True, slots=True)
class Content:
    """What an event says besides its time; an override carries its own."""

    title: str = ""
    location: str = ""
    description: str = ""  # plain text, never rendered as HTML or Markdown
    status: Status = Status.CONFIRMED
    visibility: Visibility = Visibility.DEFAULT
    busy: bool = True
    sequence: int = 0
    attendees: tuple[AttendeeDraft, ...] = ()


@dataclass(frozen=True, slots=True)
class OverrideDraft:
    """One occurrence of a series, replaced: `recurrence_id` is the wall time (in the
    series' zone; all-day: midnight) the series names it by, `series` its own time
    (no rule)."""

    recurrence_id: datetime
    series: Series
    content: Content


@dataclass(frozen=True, slots=True)
class EventDraft:
    uid: str
    series: Series
    content: Content
    organiser: str | None = None  # an address
    overrides: tuple[OverrideDraft, ...] = ()  # sorted by recurrence id
    alarms: tuple[int, ...] = ()  # minutes before the start, ascending


@dataclass(frozen=True, slots=True)
class ExportEvent:
    """An event to write: a draft's fields, the time it was last changed (`DTSTAMP`)
    and whether the reader sees only its time (`redacted`: time and "busy", nothing
    else, decision 3)."""

    uid: str
    series: Series
    content: Content
    stamp: datetime  # aware
    organiser: str | None = None
    overrides: tuple[OverrideDraft, ...] = ()
    alarms: tuple[int, ...] = ()
    redacted: bool = False

    @classmethod
    def of(cls, draft: EventDraft, *, stamp: datetime, redacted: bool = False) -> Self:
        shared = {field.name: getattr(draft, field.name) for field in fields(EventDraft)}
        return cls(**shared, stamp=stamp, redacted=redacted)
