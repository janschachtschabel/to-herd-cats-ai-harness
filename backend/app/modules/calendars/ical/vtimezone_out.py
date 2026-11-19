"""The VTIMEZONE written for a zone (review M10 Task 7a, R7a-11): it covers every year a
series of the calendar may touch (1900 to 2399), so every event of a stream is covered,
not only the first, and a client that follows the definition (Outlook) agrees with
`tzdata` for an endless series too.

- The zone's changes since the year its present rules began are two yearly rules
  (`RRULE:FREQ=YEARLY;BYMONTH=…;BYDAY=…`, a weekday in a range of days where a change
  falls at 24:00 or -1:00, or a fixed day), found from `zoneinfo`'s transitions and
  checked over a whole 28-year cycle after 2037 (`tzdata`'s last rule there). This is
  the form Outlook, Google and Apple write themselves.
- The years before are `icalendar`'s `Timezone.from_tzinfo` from 1900 (one onset per
  change, as RDATEs).
- A zone whose changes follow no yearly rule (Casablanca's until 2087) is written as
  RDATEs up to 2400; one without changes needs none.
"""

import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from icalendar import Timezone, TimezoneDaylight, TimezoneStandard
from icalendar.prop import vInline

from app.modules.calendars import zones
from app.modules.calendars.ical.vtimezone import days_of
from app.modules.calendars.recurrence_rule import FIRST_YEAR, LAST_YEAR, parse_rule

_RULE_YEAR = 2038  # beyond `tzdata`'s explicit transitions: its last rule
_CYCLE = 28  # the Gregorian weekdays repeat after 28 years (between century years)
_DAY = timedelta(days=1)
_DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


@dataclass(frozen=True, slots=True)
class _Change:
    instant: datetime  # UTC
    offset_from: timedelta
    offset_to: timedelta
    name: str

    @property
    def wall(self) -> datetime:
        """The wall time before the change (RFC 5545 3.6.5: DTSTART in TZOFFSETFROM)."""
        return (self.instant + self.offset_from).replace(tzinfo=None)


@lru_cache(maxsize=128)
def vtimezone(tzid: str) -> bytes:
    zone = zones.zone(tzid)
    rules = _rules(zone)
    if rules is None:
        return bytes(_history(zone, tzid, LAST_YEAR + 1).to_ical())
    first_year, tail = rules
    found = _history(zone, tzid, first_year) if first_year > FIRST_YEAR else _empty(tzid)
    for change, rule in tail:
        part = TimezoneDaylight() if change.offset_to > change.offset_from else TimezoneStandard()
        part.add("DTSTART", change.wall)
        part.add("RRULE", vInline(rule))
        part.add("TZNAME", change.name)
        part.add("TZOFFSETFROM", change.offset_from)
        part.add("TZOFFSETTO", change.offset_to)
        found.add_component(part)
    return bytes(found.to_ical())


def _history(zone: ZoneInfo, tzid: str, last_year: int) -> Timezone:
    found = Timezone.from_tzinfo(
        zone, tzid=tzid, first_date=date(FIRST_YEAR, 1, 1), last_date=date(last_year, 1, 1)
    )
    found.pop("COMMENT", None)  # "only works from … to …": the rules carry it on
    return found


def _empty(tzid: str) -> Timezone:
    found = Timezone()
    found.add("TZID", tzid)
    return found


def _rules(zone: ZoneInfo) -> tuple[int, list[tuple[_Change, str]]] | None:
    """The first year of the zone's present yearly rules and, for each change, its first
    onset in that year and its rule; None if the changes follow no yearly rule (or
    there are none)."""
    changes = _changes(zone, _RULE_YEAR)
    if not changes:
        return None
    tail: list[tuple[_Change, str]] = []
    for change in changes:
        rule = next((r for r in _forms(change.wall) if _holds(zone, change, r, _RULE_YEAR)), None)
        if rule is None:
            return None
        tail.append((change, rule))
    year = _RULE_YEAR
    while year > FIRST_YEAR and _matches_year(zone, tail, year - 1):
        year -= 1
    firsts = [(_in_year(zone, change, year), rule) for change, rule in tail]
    if any(first is None for first, _ in firsts):
        return None
    return year, [(first, rule) for first, rule in firsts if first is not None]


def _holds(zone: ZoneInfo, change: _Change, rule: str, year: int) -> bool:
    """Whether `rule` gives the change (same wall time, same offsets) in every year of a
    cycle from `year` on."""
    return all(_onset(zone, change, rule, y) for y in range(year, year + _CYCLE))


def _matches_year(zone: ZoneInfo, tail: list[tuple[_Change, str]], year: int) -> bool:
    changes = _changes(zone, year)
    return len(changes) == len(tail) and all(_onset(zone, c, r, year) for c, r in tail)


def _onset(zone: ZoneInfo, change: _Change, rule: str, year: int) -> bool:
    found = _in_year(zone, change, year)
    return found is not None and found.wall.date() == _rule_day(rule, year, change.wall.month)


def _in_year(zone: ZoneInfo, change: _Change, year: int) -> _Change | None:
    """The change of `year` with `change`'s offsets and wall time of day."""
    return next(
        (
            c
            for c in _changes(zone, year)
            if (c.offset_from, c.offset_to) == (change.offset_from, change.offset_to)
            and c.wall.time() == change.wall.time()
        ),
        None,
    )


def _forms(wall: datetime) -> list[str]:
    """The yearly rules a change on `wall`'s day may follow."""
    day, month = wall.day, wall.month
    weekday = _DAYS[wall.weekday()]
    last = calendar.monthrange(wall.year, month)[1]
    shortest = calendar.monthrange(2001, month)[1]  # the month in a common year
    head = f"FREQ=YEARLY;BYMONTH={month}"
    forms = []
    if day <= 28:
        forms.append(f"{head};BYDAY={(day - 1) // 7 + 1}{weekday}")
    if day > last - 7:
        forms.append(f"{head};BYDAY=-1{weekday}")
    for first in range(max(1, day - 6), day + 1):
        if first + 6 <= shortest:
            days = ",".join(str(d) for d in range(first, first + 7))
            forms.append(f"{head};BYDAY={weekday};BYMONTHDAY={days}")
    forms.append(f"{head};BYMONTHDAY={day}")
    return forms


def _rule_day(rule: str, year: int, month: int) -> date | None:
    found = days_of(parse_rule(rule), year, month)
    return date(year, month, found[0]) if len(found) == 1 else None


@lru_cache(maxsize=4096)
def _changes(zone: ZoneInfo, year: int) -> tuple[_Change, ...]:
    """The zone's changes of offset in `year` (a day apart at least), by instant."""
    found: list[_Change] = []
    moment = datetime(year, 1, 1, tzinfo=UTC)
    end = datetime(year + 1, 1, 1, tzinfo=UTC)
    before = _offset(zone, moment)
    while moment < end:
        later = moment + _DAY
        after = _offset(zone, later)
        if after != before:
            instant = _bisect(zone, moment, later, before)
            name = instant.astimezone(zone).tzname() or ""
            found.append(_Change(instant, before, after, name))
        moment, before = later, after
    return tuple(found)


def _bisect(zone: ZoneInfo, lo: datetime, hi: datetime, before: timedelta) -> datetime:
    """The first instant in `(lo, hi]` with another offset than `before` (to the second)."""
    while hi - lo > timedelta(seconds=1):
        middle = lo + (hi - lo) / 2
        middle = middle.replace(microsecond=0)
        if _offset(zone, middle) == before:
            lo = middle
        else:
            hi = middle
    return hi


def _offset(zone: ZoneInfo, moment: datetime) -> timedelta:
    offset = moment.astimezone(zone).utcoffset()
    assert offset is not None
    return offset
