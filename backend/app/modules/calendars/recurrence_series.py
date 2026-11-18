"""A series' shape and its time arithmetic (plan M10 decision 6): pure, no library.
`recurrence` expands it and re-exports `Series` and `Occurrence`.

Series lie in the years 1900 to 2399: start, RDATEs, UNTIL and the master's end
(`event.time_out_of_range` otherwise). Every occurrence therefore starts between
`EARLIEST` and `LATEST`, so an instant outside them can be moved to them without
changing any answer (`bounded`), and no arithmetic leaves `datetime`'s range.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from app.modules.calendars import zones
from app.modules.calendars.recurrence_rule import (
    FIRST_YEAR,
    LAST_YEAR,
    ParsedRule,
    RuleInvalid,
    SeriesInvalid,
    parse_rule,
)

DAY = timedelta(days=1)
# Offsets of one zone stay within a day of UTC: every occurrence starts in between.
EARLIEST = datetime(FIRST_YEAR - 1, 1, 1, tzinfo=UTC)
LATEST = datetime(LAST_YEAR + 2, 1, 1, tzinfo=UTC)
_END = datetime(LAST_YEAR + 1, 1, 1)  # the latest wall time a master may end at


@dataclass(frozen=True, slots=True)
class Occurrence:
    start: datetime  # UTC
    end: datetime  # UTC
    recurrence_id: datetime  # the wall time the series names it by


@dataclass(frozen=True, slots=True)
class Series:
    start: datetime  # wall time in `tzid`; all-day: 00:00 of the first day
    duration: timedelta
    tzid: str | None  # None for all-day
    all_day: bool
    rrule: str | None = None
    rdates: tuple[datetime, ...] = ()  # wall times
    exdates: tuple[datetime, ...] = ()  # wall times

    def __post_init__(self) -> None:
        _check_shape(self)

    @property
    def rule(self) -> ParsedRule | None:
        return parse_rule(self.rrule) if self.rrule else None


def _check_shape(series: Series) -> None:
    walls = (series.start, *series.rdates, *series.exdates)
    if any(w.tzinfo is not None or w.microsecond for w in walls) or series.duration < timedelta():
        raise SeriesInvalid("event.invalid_time")
    if series.all_day:
        whole = series.duration >= DAY and series.duration % DAY == timedelta()
        if series.tzid is not None or not whole or any(w.time() != time() for w in walls):
            raise SeriesInvalid("event.invalid_time")
    else:
        try:
            zones.zone(series.tzid or "")
        except zones.ZoneUnknown:
            raise SeriesInvalid("event.invalid_time_zone") from None
    if any(not FIRST_YEAR <= w.year <= LAST_YEAR for w in (series.start, *series.rdates)):
        raise SeriesInvalid("event.time_out_of_range")
    if series.duration > _END - series.start:
        raise SeriesInvalid("event.time_out_of_range")
    rule = series.rule
    if rule is not None and rule.until is not None:
        if isinstance(rule.until, datetime) == series.all_day:
            raise RuleInvalid("event.rrule_invalid")  # zone: UNTIL in UTC; all-day: a date


def instant(series: Series, wall: datetime) -> datetime:
    """The instant (UTC) of the wall time `wall` of the series."""
    if series.tzid is None:
        return wall.replace(tzinfo=UTC)
    return zones.localise(wall, series.tzid)


def wall_of(series: Series, moment: datetime) -> datetime:
    """The series' wall time of the instant `moment` (aware)."""
    if moment.tzinfo is None:
        raise ValueError("an instant is aware")
    if series.tzid is None:
        return moment.astimezone(UTC).replace(tzinfo=None)
    return zones.wall(moment, series.tzid)


def as_wall(series: Series, recurrence_id: datetime) -> datetime:
    """A recurrence id as a wall time: a naive one as it is, an aware one read as the
    series' wall time of that instant (for an occurrence in a gap that is not its id:
    `recurrence.recurrence_id_at` finds that)."""
    if recurrence_id.tzinfo is None:
        return recurrence_id
    return wall_of(series, bounded(recurrence_id))


def bounded(moment: datetime) -> datetime:
    """`moment` (aware) moved into `[EARLIEST, LATEST]`, where every occurrence starts."""
    if moment.tzinfo is None:
        raise ValueError("an instant is aware")
    return min(max(moment, EARLIEST), LATEST)
