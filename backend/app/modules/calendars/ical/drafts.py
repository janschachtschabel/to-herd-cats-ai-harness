"""An event as iCalendar carries it (plan M10 decisions 5 and 10): what reading gives
and what writing takes. Pure data; times are `recurrence.Series` (wall times in the
series' zone, all-day on midnights), so a draft expands like a stored event.

The values follow decision 5 (`status`, `visibility`, `busy`) and 7 (an attendee's
role and response); the limits are decision 5's (title, place, text, 100 attendees)
and 8's (three reminders, at most four weeks before).
"""

from dataclasses import dataclass
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
MAX_OVERRIDES = 1000  # per series; reading counts the rest as `ical.over_limit`
MAX_RDATES = 1000  # values written per series; reading counts the rest (once per event)


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
class ExportOverride:
    """An override to write, with its own decision (decision 6, I6: an override is a
    row with its own visibility and attendees): `redacted` writes only its time and
    "busy", whatever the series shows."""

    recurrence_id: datetime
    series: Series
    content: Content
    redacted: bool = False


@dataclass(frozen=True, slots=True)
class ExportEvent:
    """An event to write: a draft's fields, the time it was last changed (`DTSTAMP`)
    and whether the reader sees only its time (`redacted`: time and "busy", nothing
    else, decision 3). A redacted series is written under `opaque_uid`, which the
    caller makes with `opaque.opaque_uid` (a keyed hash: nobody can confirm a guessed
    UID, R7a-5); it is required then."""

    uid: str
    series: Series
    content: Content
    stamp: datetime  # aware
    organiser: str | None = None
    overrides: tuple[ExportOverride, ...] = ()
    alarms: tuple[int, ...] = ()
    redacted: bool = False
    opaque_uid: str | None = None

    def __post_init__(self) -> None:
        if self.stamp.tzinfo is None:
            raise ValueError("the stamp must be aware: it is never read in the process's zone")
        if self.redacted and not self.opaque_uid:
            raise ValueError("a redacted event is written under its opaque UID only")

    @classmethod
    def of(
        cls,
        draft: EventDraft,
        *,
        stamp: datetime,
        redacted: bool = False,
        opaque_uid: str | None = None,
    ) -> Self:
        """`draft` to write; its overrides take the series' decision (build
        `ExportOverride`s for one of their own)."""
        overrides = tuple(
            ExportOverride(o.recurrence_id, o.series, o.content, redacted=redacted)
            for o in draft.overrides
        )
        return cls(
            uid=draft.uid,
            series=draft.series,
            content=draft.content,
            stamp=stamp,
            organiser=draft.organiser,
            overrides=overrides,
            alarms=draft.alarms,
            redacted=redacted,
            opaque_uid=opaque_uid,
        )
