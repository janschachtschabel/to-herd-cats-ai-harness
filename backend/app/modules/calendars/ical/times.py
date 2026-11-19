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
  that instant's day in UTC (RFC 5545 3.3.10: the day's midnight, at which the series
  floats, is compared with it), the same in every calendar (R7a-9). An `UNTIL` past
  2399 ends nothing a series of the calendar has, so it is dropped; one before 1900
  ends the series at its start.
- An EXDATE or RDATE as a date for a series with a time means that day at the series'
  time; one in another zone or in UTC means the series' wall time of that instant, or
  the occurrence in a gap that starts at it (`moments`, R7a-6).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from app.modules.calendars import zones
from app.modules.calendars.ical import lines, problems
from app.modules.calendars.ical import zones as ical_zones
from app.modules.calendars.ical.budget import Budget, OverBudget
from app.modules.calendars.ical.problems import Skip
from app.modules.calendars.ical.zones import Resolver
from app.modules.calendars.recurrence_rule import (
    FIRST_YEAR,
    LAST_YEAR,
    Freq,
    RuleInvalid,
    parse_rule,
)

DAY = timedelta(days=1)
_UNTIL = re.compile(r"(?i)^(\s*UNTIL\s*=\s*)([0-9]{8}(?:T[0-9]{6}Z?)?)\s*$")
_EARLIEST = datetime(FIRST_YEAR, 1, 1, tzinfo=UTC)
_WALL_PROPS = ("DTSTART", "DTEND", "RDATE", "EXDATE", "RECURRENCE-ID")
# The wall times a VTIMEZONE is checked at for one event (R7a-1): enough to find a
# definition that departs from a zone at the event's times, not one check per EXDATE.
MAX_ZONE_WALLS = 32


@dataclass(slots=True)
class Frame:
    """What the times of one event (its series and overrides) are read against: each
    TZID resolves once per event (R7a-1), against at most `MAX_ZONE_WALLS` of the wall
    times written in it (the first written, then a spread of the rest)."""

    default_zone: str
    resolver: Resolver
    walls: dict[str, list[datetime]]  # per TZID, the wall times written in it (sampled)
    years: dict[str, tuple[int, ...]]  # per TZID, the years its VTIMEZONE is compared in
    budget: Budget
    _zones: dict[str, str] = field(default_factory=dict)  # a zone, or a problem code

    @classmethod
    def of(
        cls,
        default_zone: str,
        resolver: Resolver,
        parts: Iterable[lines.Component],
        budget: Budget,
    ) -> "Frame":
        walls: dict[str, list[datetime]] = {}
        end: int | None = None  # the year a rule ends in (at the latest)
        for part in parts:
            rule = part.first("RRULE")
            if rule is not None and (start := part.first("DTSTART")) is not None:
                end = _rule_end(rule.raw, start.raw)
            for name in _WALL_PROPS:
                for prop in part.all(name):
                    tzid = prop.param("TZID")
                    if tzid is None:
                        continue
                    try:
                        values = lines.date_times(prop)
                    except Skip:
                        continue
                    found = [v for v in values if isinstance(v, datetime)]
                    if found:
                        walls.setdefault(tzid, []).extend(found)
        spans = {
            tzid: ical_zones.years(values[0].year, max(end or 0, *(v.year for v in values)))
            for tzid, values in walls.items()
        }
        return cls(default_zone, resolver, {k: _spread(v) for k, v in walls.items()}, spans, budget)

    def zone(self, tzid: str) -> str:
        if tzid not in self._zones:
            try:
                self._zones[tzid] = self.resolver.resolve(
                    tzid, self.walls.get(tzid, []), self.years.get(tzid, ()), self.budget
                )
            except Skip as skip:
                self._zones[tzid] = skip.code
        found = self._zones[tzid]
        if found == problems.OVER_BUDGET:
            raise OverBudget()
        if found in problems.CODES:
            raise Skip(found)
        return found


def _rule_end(rule: str, start: str) -> int | None:
    """The year a rule written at the start `start` ends in at the latest (its UNTIL,
    or its COUNT of whole periods); None if it cannot be read; endless: the last year."""
    try:
        parsed = parse_rule(rule.strip().removeprefix("RRULE:"))
        first = lines.date_time(start.split(",", 1)[0]).year
    except (RuleInvalid, Skip):
        return None
    if parsed.until is not None:
        return parsed.until.year
    if parsed.count is None:
        return LAST_YEAR
    days = {Freq.DAILY: 1, Freq.WEEKLY: 7, Freq.MONTHLY: 31, Freq.YEARLY: 366}[parsed.freq]
    return min(first + parsed.count * parsed.interval * days // 365 + 1, LAST_YEAR)


def _spread(walls: list[datetime]) -> list[datetime]:
    """The first wall time (the start), then at most `MAX_ZONE_WALLS - 1` of the others,
    spread evenly over them in order."""
    if len(walls) <= MAX_ZONE_WALLS:
        return walls
    rest = sorted(set(walls[1:]))
    room = MAX_ZONE_WALLS - 1
    if len(rest) <= room:
        return [walls[0], *rest]
    return [walls[0], *(rest[index * (len(rest) - 1) // (room - 1)] for index in range(room))]


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
    try:
        return _length(part, begin, frame)
    except OverflowError:  # `DURATION:P999999W` leaves `datetime`'s years
        raise Skip(problems.TIME_OUT_OF_RANGE) from None


def _length(part: lines.Component, begin: Start, frame: Frame) -> timedelta:
    end = part.first("DTEND")
    if end is not None:
        value = _first(end)
        if begin.all_day:
            days = (_day_of(value, end.param("TZID"), frame) - begin.wall.date()).days
            return DAY * max(days, 1)
        found = _instant(value, end.param("TZID"), begin.tzid or "UTC", frame) - begin.instant
    elif (written := part.first("DURATION")) is not None:
        days, exact = lines.duration(written.raw)
        if days < 0 or exact < timedelta():
            raise Skip(problems.TIME_INVALID)
        if begin.all_day:
            return DAY * max(days + -(-exact // DAY), 1)
        # whole days are nominal (RFC 5545 3.3.6): the same wall time days later
        nominal = _localise(begin.wall + timedelta(days=days), begin.tzid or "UTC")
        found = nominal + exact - begin.instant
    else:
        return DAY if begin.all_day else timedelta()
    if found < timedelta():
        raise Skip(problems.TIME_INVALID)
    return found


def walls(prop: lines.Prop, begin: Start, frame: Frame) -> list[datetime]:
    """The values of `prop` (RDATE, EXDATE, RECURRENCE-ID) as wall times of the
    series that starts at `begin`."""
    return [wall for wall, _ in moments(prop, begin, frame)]


def moments(prop: lines.Prop, begin: Start, frame: Frame) -> list[tuple[datetime, datetime | None]]:
    """`walls`, each with the instant it was read from when the file named one (UTC or
    another zone than the series'): an occurrence in a gap is named by an instant
    whose wall time is not its recurrence id (R7a-6)."""
    tzid = prop.param("TZID")
    return [_moment(value, tzid, begin, frame) for value in lines.date_times(prop)]


def _moment(
    value: date | datetime, tzid: str | None, begin: Start, frame: Frame
) -> tuple[datetime, datetime | None]:
    wall = to_wall(value, tzid, begin, frame)
    if begin.all_day or not isinstance(value, datetime):
        return wall, None
    series_zone = begin.tzid or "UTC"
    if value.tzinfo is None and (tzid is None or frame.zone(tzid) == series_zone):
        return wall, None
    return wall, _instant(value, tzid, series_zone, frame)


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
        if written.year > LAST_YEAR:
            del parts[index]
            return ";".join(parts)
        if written.year < FIRST_YEAR:  # ends the series at its start
            written = date(FIRST_YEAR, 1, 1) if begin.all_day else _EARLIEST
        if begin.all_day:  # occurrences float at midnight UTC: the instant's UTC day
            day = written.astimezone(UTC).date() if isinstance(written, datetime) else written
            moment = datetime.combine(day, time(), tzinfo=UTC)
        elif isinstance(written, datetime):
            moment = written if written.tzinfo else _localise(written, begin.tzid or "UTC")
        else:
            moment = _localise(datetime.combine(written, time(23, 59, 59)), begin.tzid or "UTC")
        if moment.year > LAST_YEAR:
            del parts[index]
            return ";".join(parts)
        moment = max(moment, _EARLIEST)
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
