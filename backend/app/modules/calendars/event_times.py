"""An event's times as the API takes them, checked into what is stored, and a stored
event as the `Series` it is expanded from (plan M10 decisions 5 and 6).

- An event with a time of day names its start and end as instants and an IANA zone
  (the calendar's when it names none); its series runs in the zone's wall time of its
  start (`zones.wall`: a future `tzdata` change leaves a series that began before it
  at its wall time, so its EXDATEs and overrides keep matching).
- An all-day event names its first and last day; it floats on 00:00 UTC of the first
  day and of the day after the last (`zones.all_day_bounds`), without a zone.
- RDATEs and EXDATEs are wall times (naive) of the series; no RDATE lies before the
  start (the window loads a series from its start on).
- Instants are aware (naive: `event.invalid_time`) and lie in the years 1900 to 2399
  as sent (`event.time_out_of_range`), so nothing overflows.
- One event lasts at most `MAX_DURATION` (`event.too_long`), and no occurrence of a
  series lasts past the start of the next (`recurrence_gaps`, `event.series_overlaps`),
  so no event fills a window with copies of itself.
- Every write path checks its series here (`recurrence.check_series`); a problem is
  422 with the problem's code (`event.invalid_time`, `event.invalid_time_zone`,
  `event.time_out_of_range`, `event.too_long`, `event.series_overlaps`,
  `event.rrule_invalid`, `event.rrule_unsupported`).
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from app.core.errors import ValidationFailed
from app.modules.calendars import recurrence, zones
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.recurrence import FIRST_YEAR, LAST_YEAR, Series
from app.modules.calendars.recurrence_gaps import overlaps_itself

# The longest one event may last (review M10 task 3a, R3a-1): a year and a day, so a
# whole leap year fits, all-day or not.
MAX_DURATION = timedelta(days=366)


@dataclass(frozen=True, slots=True)
class Times:
    """What the client sent about when."""

    all_day: bool = False
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    first_day: date | None = None
    last_day: date | None = None
    tzid: str | None = None
    rrule: str | None = None
    rdates: tuple[datetime, ...] = ()
    exdates: tuple[datetime, ...] = ()


@dataclass(frozen=True, slots=True)
class Checked:
    """What is stored about when."""

    starts_at: datetime
    ends_at: datetime
    tzid: str | None
    rrule: str | None  # canonical
    rdates: tuple[datetime, ...]
    exdates: tuple[datetime, ...]
    recurs_until: datetime | None


def invalid(code: str) -> ValidationFailed:
    return ValidationFailed(code=code)


def _bounds(times: Times, default_zone: str) -> tuple[datetime, datetime, datetime, str | None]:
    """(starts_at, ends_at, wall start, zone)."""
    if times.all_day:
        if times.starts_at or times.ends_at or times.tzid or not times.first_day:
            raise invalid("event.invalid_time")
        if not times.last_day or times.last_day < times.first_day:
            raise invalid("event.invalid_time")
        try:
            first, after = zones.all_day_bounds(times.first_day, times.last_day)
        except OverflowError:
            raise invalid("event.time_out_of_range") from None
        return first, after, first.replace(tzinfo=None), None
    starts_at, ends_at = times.starts_at, times.ends_at
    if times.first_day or times.last_day or not starts_at or not ends_at:
        raise invalid("event.invalid_time")
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise invalid("event.invalid_time")  # an instant names its offset
    if not (in_years(starts_at) and in_years(ends_at)):
        raise invalid("event.time_out_of_range")
    if ends_at < starts_at:
        raise invalid("event.invalid_time")
    tzid = times.tzid or default_zone
    try:
        wall = zones.wall(starts_at, tzid)
    except zones.ZoneUnknown:
        raise invalid("event.invalid_time_zone") from None
    return starts_at.astimezone(UTC), ends_at.astimezone(UTC), wall, tzid


def in_years(moment: datetime) -> bool:
    """Whether the aware `moment`, read in the offset it came with, lies in the years
    a series may (1900 to 2399; `recurrence_series`): within a day of them in UTC, so
    no arithmetic on it leaves `datetime`."""
    return FIRST_YEAR <= moment.year <= LAST_YEAR


def check(times: Times, default_zone: str) -> Checked:
    """The stored form of `times`, or 422 with the problem's code."""
    starts_at, ends_at, wall, tzid = _bounds(times, default_zone)
    if any(d.tzinfo is None and d < wall for d in times.rdates):
        raise invalid("event.invalid_time")
    try:
        series = Series(
            start=wall,
            duration=ends_at - starts_at,
            tzid=tzid,
            all_day=times.all_day,
            rrule=times.rrule,
            rdates=times.rdates,
            exdates=times.exdates,
        )
        recurrence.check_series(series)
        rule = recurrence.check_rule(times.rrule) if times.rrule else None
    except recurrence.SeriesInvalid as exc:
        raise invalid(exc.code) from None
    if series.duration > MAX_DURATION:
        raise invalid("event.too_long")
    recurring = rule is not None or bool(times.rdates)
    if recurring and overlaps_itself(series):
        raise invalid("event.series_overlaps")
    return Checked(
        starts_at=starts_at,
        ends_at=ends_at,
        tzid=tzid,
        rrule=rule,
        rdates=tuple(sorted(set(times.rdates))),
        exdates=tuple(sorted(set(times.exdates))),
        recurs_until=recurrence.last_end(series) if recurring else ends_at,
    )


def series_of(event: CalendarEvent) -> Series:
    """The stored event as the series it is expanded from (`SeriesInvalid` if what is
    stored no longer makes one, e.g. a zone `tzdata` dropped)."""
    if event.all_day or event.tzid is None:
        start = event.starts_at.astimezone(UTC).replace(tzinfo=None)
    else:
        start = zones.wall(event.starts_at, event.tzid)
    return Series(
        start=start,
        duration=event.ends_at - event.starts_at,
        tzid=None if event.all_day else event.tzid,
        all_day=event.all_day,
        rrule=event.rrule,
        rdates=tuple(event.rdates),
        exdates=tuple(event.exdates),
    )


def days_of(event: CalendarEvent) -> tuple[date, date] | None:
    """An all-day event's first and last day."""
    if not event.all_day:
        return None
    first = event.starts_at.astimezone(UTC).date()
    return first, (event.ends_at.astimezone(UTC) - timedelta(days=1)).date()


def floating_day(moment: datetime, zone: str) -> datetime:
    """The instant the floating day starting at `moment` (00:00 UTC) starts in `zone`."""
    return zones.localise(datetime.combine(moment.astimezone(UTC).date(), time()), zone)
