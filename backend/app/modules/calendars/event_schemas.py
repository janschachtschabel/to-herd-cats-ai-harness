"""Events as the API takes and shows them. What a caller sees only as "busy" (`sight`
`BUSY`) comes `redacted`: without title, place, text, UID and organiser, in every
answer (decision 3)."""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.core.principal import PrincipalType
from app.modules.calendars.event_models import (
    DATES_MAX,
    DESCRIPTION_MAX,
    LOCATION_MAX,
    RRULE_MAX,
    TITLE_MAX,
    TZID_MAX,
    UID_MAX,
    CalendarEvent,
    EventStatus,
    EventVisibility,
)
from app.modules.calendars.event_times import Times, days_of
from app.modules.calendars.events import NewEvent
from app.modules.calendars.recurrence import Occurrence
from app.modules.calendars.sight import Sight

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX)]


class EventCreate(BaseModel):
    """An event with a time of day names `starts_at`, `ends_at` (instants) and its
    `tzid` (default: the calendar's zone); an all-day one `all_day`, `first_day` and
    `last_day`. `rrule` (RFC 5545, `DAILY` or slower), `rdates` and `exdates` (wall
    times in the event's zone, without offset) make it a series. `busy` defaults to
    true, for all-day events to false."""

    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Annotated[str, StringConstraints(max_length=DESCRIPTION_MAX)] = ""
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=LOCATION_MAX)] = ""
    all_day: bool = False
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    first_day: date | None = None
    last_day: date | None = None
    tzid: Annotated[str, StringConstraints(max_length=TZID_MAX)] | None = None
    rrule: Annotated[str, StringConstraints(max_length=RRULE_MAX)] | None = None
    rdates: list[datetime] = Field(default_factory=list, max_length=DATES_MAX)
    exdates: list[datetime] = Field(default_factory=list, max_length=DATES_MAX)
    status: EventStatus = EventStatus.CONFIRMED
    visibility: EventVisibility = EventVisibility.DEFAULT
    busy: bool | None = None
    uid: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=UID_MAX)]
        | None
    ) = None

    def new(self) -> NewEvent:
        times = Times(
            all_day=self.all_day,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
            first_day=self.first_day,
            last_day=self.last_day,
            tzid=self.tzid,
            rrule=self.rrule,
            rdates=tuple(self.rdates),
            exdates=tuple(self.exdates),
        )
        return NewEvent(
            title=self.title,
            times=times,
            description=self.description,
            location=self.location,
            status=self.status,
            visibility=self.visibility,
            busy=self.busy,
            uid=self.uid,
        )


class OrganizerOut(BaseModel):
    type: PrincipalType
    id: uuid.UUID


class EventOut(BaseModel):
    """`starts_at`/`ends_at`: the first occurrence (all-day: 00:00 UTC of `first_day`
    and of the day after `last_day`). `recurs_until`: when the last occurrence ends
    (null: endless). `series_id`: for an override (one occurrence changed on its own),
    the series it belongs to; null otherwise. `redacted`: the caller sees only times
    and "busy"; content fields are null."""

    id: uuid.UUID
    calendar_id: uuid.UUID
    space_id: uuid.UUID
    series_id: uuid.UUID | None
    uid: str | None
    title: str | None
    description: str | None
    location: str | None
    all_day: bool
    starts_at: datetime
    ends_at: datetime
    first_day: date | None
    last_day: date | None
    tzid: str | None
    rrule: str | None
    rdates: list[datetime]
    exdates: list[datetime]
    recurs_until: datetime | None
    status: EventStatus
    visibility: EventVisibility
    busy: bool
    organizer: OrganizerOut | None
    redacted: bool
    version: int

    @classmethod
    def of(cls, event: CalendarEvent, seen: Sight) -> "EventOut":
        full = seen is Sight.FULL
        days = days_of(event)
        return cls(
            id=event.id,
            calendar_id=event.calendar_id,
            space_id=event.space_id,
            series_id=event.series_id,
            uid=event.uid if full else None,
            title=event.title if full else None,
            description=event.description if full else None,
            location=event.location if full else None,
            all_day=event.all_day,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            first_day=days[0] if days else None,
            last_day=days[1] if days else None,
            tzid=event.tzid,
            rrule=event.rrule,
            rdates=list(event.rdates),
            exdates=list(event.exdates),
            recurs_until=event.recurs_until,
            status=EventStatus(event.status),
            visibility=EventVisibility(event.visibility),
            busy=event.busy,
            organizer=OrganizerOut(type=event.organizer_type, id=event.organizer_id)
            if full
            else None,
            redacted=not full,
            version=event.version,
        )


class OccurrenceOut(BaseModel):
    """One occurrence in the window. `recurrence_id`: for an occurrence of a series,
    the wall time it is named by (ISO 8601 without offset), which changing or deleting
    just this one takes back (task 3b); null for an event that is no series.
    `series_id`: for an override, which is listed as an event of its own, the series
    it belongs to (to change the whole series from it); null otherwise. `redacted`:
    the caller sees only times and "busy" (`title`, `location` null)."""

    event_id: uuid.UUID
    calendar_id: uuid.UUID
    space_id: uuid.UUID
    series_id: uuid.UUID | None
    start: datetime
    end: datetime
    all_day: bool
    recurring: bool
    recurrence_id: str | None
    title: str | None
    location: str | None
    status: EventStatus
    visibility: EventVisibility
    busy: bool
    redacted: bool

    @classmethod
    def of(cls, event: CalendarEvent, occurrence: Occurrence, seen: Sight) -> "OccurrenceOut":
        full = seen is Sight.FULL
        return cls(
            event_id=event.id,
            calendar_id=event.calendar_id,
            space_id=event.space_id,
            series_id=event.series_id,
            start=occurrence.start,
            end=occurrence.end,
            all_day=event.all_day,
            recurring=event.recurring,
            recurrence_id=occurrence.recurrence_id.isoformat() if event.recurring else None,
            title=event.title if full else None,
            location=event.location if full else None,
            status=EventStatus(event.status),
            visibility=EventVisibility(event.visibility),
            busy=event.busy,
            redacted=not full,
        )
