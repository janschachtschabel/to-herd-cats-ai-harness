"""The times of one event as the calendar keeps them (plan M10 decision 10: "Lesen ist
nachsichtig"): a start in its zone, an exact duration, and every RDATE, EXDATE and
RECURRENCE-ID as a wall time of the series, whatever form the file wrote them in.

- A start with a TZID is a wall time in the zone it resolves to (`zones.Resolver`);
  a floating one is read in the calendar's zone (`default_zone`); one in UTC keeps its
  instant: a single event takes the calendar's zone, a series recurs in UTC (RFC 5545:
  a UTC start repeats at the same UTC time).
- A DATE start is all-day; an end before the start is `ical.time_invalid`.
- `UNTIL` as a date for a start with a time ends after that day in the series' zone;
  as a local time it is read in that zone; as an instant for an all-day series it is
  that instant's day in the calendar's zone. An `UNTIL` past 2399 ends nothing a series
  of the calendar has, so it is dropped; one before 1900 ends the series at its start.
- An EXDATE or RDATE as a date for a series with a time means that day at the series'
  time; one in another zone or in UTC means the series' wall time of that instant.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from app.modules.calendars import zones
from app.modules.calendars.ical import lines, problems
from app.modules.calendars.ical.problems import Skip
from app.modules.calendars.ical.zones import Resolver
from app.modules.calendars.recurrence_rule import FIRST_YEAR, LAST_YEAR

DAY = timedelta(days=1)
_UNTIL = re.compile(r"(?i)^(\s*UNTIL\s*=\s*)([0-9]{8}(?:T[0-9]{6}Z?)?)\s*$")
_WALL_PROPS = ("DTSTART", "DTEND", "RDATE", "EXDATE", "RECURRENCE-ID")


@dataclass(frozen=True, slots=True)
class Frame:
    """What the times of one event (its series and overrides) are read against."""

    default_zone: str
    resolver: Resolver
    walls: dict[str, list[datetime]]  # per TZID, the wall times written in it

    @classmethod
    def of(cls, default_zone: str, resolver: Resolver, parts: Iterable[lines.Component]) -> "Frame":
        walls: dict[str, list[datetime]] = {}
        for part in parts:
            for name in _WALL_PROPS:
                for prop in part.all(name):
                    tzid = prop.param("TZID")
                    if tzid is None:
                        continue
                    try:
                        values = lines.date_times(prop)
                    except Skip:
                        continue
                    walls.setdefault(tzid, []).extend(v for v in values if isinstance(v, datetime))
        return cls(default_zone, resolver, walls)

    def zone(self, tzid: str) -> str:
        return self.resolver.resolve(tzid, self.walls.get(tzid, []))


@dataclass(frozen=True, slots=True)
class Start:
    wall: datetime  # naive; all-day: midnight
    tzid: str | None  # None for all-day
    instant: datetime  # UTC; all-day: midnight UTC

    @property
    def all_day(self) -> bool:
        return self.tzid is None


def start(part: lines.Component, frame: Frame, *, recurring: bool) -> Start:
    prop = part.first("DTSTART")
    if prop is None:
        raise Skip(problems.TIME_INVALID)
    value = _first(prop)
    if not isinstance(value, datetime):
        wall = datetime.combine(value, time())
        return Start(wall, None, wall.replace(tzinfo=UTC))
    if value.tzinfo is not None:
        tzid = "UTC" if recurring else frame.default_zone
        return Start(_wall_in(value, tzid), tzid, value)
    tzid_param = prop.param("TZID")
    tzid = frame.zone(tzid_param) if tzid_param is not None else frame.default_zone
    return Start(value, tzid, _localise(value, tzid))


def length(part: lines.Component, begin: Start, frame: Frame) -> timedelta:
    """The exact duration from DTEND or DURATION; none: a day, or no time at all."""
    end = part.first("DTEND")
    if end is not None:
        value = _first(end)
        if begin.all_day:
            days = (_day_of(value, end.param("TZID"), frame) - begin.wall.date()).days
            return DAY * max(days, 1)
        found = _instant(value, end.param("TZID"), begin.tzid or "UTC", frame) - begin.instant
    elif (written := part.first("DURATION")) is not None:
        found = lines.duration(written.raw)
        if found < timedelta():
            raise Skip(problems.TIME_INVALID)
        if begin.all_day:
            return DAY * max(-(-found // DAY), 1)
        # whole days are nominal (RFC 5545 3.3.6): the same wall time days later
        nominal = begin.wall + timedelta(days=found.days)
        found = (
            _localise(nominal, begin.tzid or "UTC")
            + timedelta(seconds=found.seconds)
            - begin.instant
        )
    else:
        return DAY if begin.all_day else timedelta()
    if found < timedelta():
        raise Skip(problems.TIME_INVALID)
    return found


def walls(prop: lines.Prop, begin: Start, frame: Frame) -> list[datetime]:
    """The values of `prop` (RDATE, EXDATE, RECURRENCE-ID) as wall times of the
    series that starts at `begin`."""
    return [to_wall(value, prop.param("TZID"), begin, frame) for value in lines.date_times(prop)]


def to_wall(value: date | datetime, tzid: str | None, begin: Start, frame: Frame) -> datetime:
    if begin.all_day:
        return datetime.combine(_day_of(value, tzid, frame), time())
    if not isinstance(value, datetime):
        return datetime.combine(value, begin.wall.time())
    series_zone = begin.tzid or "UTC"
    if value.tzinfo is None and (tzid is None or frame.zone(tzid) == series_zone):
        return value
    return _wall_in(_instant(value, tzid, series_zone, frame), series_zone)


def until(rule: str, begin: Start, frame: Frame) -> str:
    """`rule` with its UNTIL in the form the series takes (see the module)."""
    parts = rule.strip().removeprefix("RRULE:").split(";")
    for index, part in enumerate(parts):
        match = _UNTIL.match(part)
        if match is None:
            continue
        written = lines.date_time(match.group(2))
        if begin.all_day:
            day = _day_of(written, None, frame)
            moment = datetime.combine(day, time(), tzinfo=UTC)
        elif isinstance(written, datetime):
            moment = written if written.tzinfo else _localise(written, begin.tzid or "UTC")
        else:
            moment = _localise(datetime.combine(written, time(23, 59, 59)), begin.tzid or "UTC")
        if moment.year > LAST_YEAR:
            del parts[index]
            return ";".join(parts)
        moment = max(moment, datetime(FIRST_YEAR, 1, 1, tzinfo=UTC))
        text = moment.strftime("%Y%m%d") if begin.all_day else moment.strftime("%Y%m%dT%H%M%SZ")
        parts[index] = f"UNTIL={text}"
        return ";".join(parts)
    return rule


def _first(prop: lines.Prop) -> date | datetime:
    values = lines.date_times(prop)
    if not values:
        raise Skip(problems.TIME_INVALID)
    return values[0]


def _day_of(value: date | datetime, tzid: str | None, frame: Frame) -> date:
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is not None:
        return _wall_in(value, frame.default_zone).date()
    return value.date()  # a wall time in its zone, or floating


def _instant(
    value: date | datetime, tzid: str | None, fallback_zone: str, frame: Frame
) -> datetime:
    if not isinstance(value, datetime):
        return _localise(datetime.combine(value, time()), fallback_zone)
    if value.tzinfo is not None:
        return value
    return _localise(value, frame.zone(tzid) if tzid is not None else fallback_zone)


def _localise(wall: datetime, tzid: str) -> datetime:
    try:
        return zones.localise(wall, tzid)
    except ValueError:
        raise Skip(problems.TIME_OUT_OF_RANGE) from None


def _wall_in(instant: datetime, tzid: str) -> datetime:
    try:
        return zones.wall(instant, tzid)
    except ValueError:
        raise Skip(problems.TIME_OUT_OF_RANGE) from None
