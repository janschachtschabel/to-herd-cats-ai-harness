"""Which IANA zone a file's TZID means (plan M10 decision 10), per file and never
through `icalendar`'s process-wide zone cache:

1. an IANA name (also with the slashes some producers put around it);
2. the library's table of Windows names (`W. Europe Standard Time` → `Europe/Berlin`);
3. the Olson name at the end of a "globally unique" TZID
   (`/mozilla.org/20050126_1/America/New_York`, RFC 5545 3.2.19);
4. the file's VTIMEZONE compared with `tzdata`: the first zone that has the same
   offset from UTC at every week of the event's year at noon and at the event's own
   times. Tried first is the definition's `X-LIC-LOCATION`, then the table's Windows
   zones (one well-known city per region), then the other regional zones, then the
   rest (`Etc/…`, `CET`), each group by name, so the choice is the same every time.

Nothing matches: `ical.time_zone_unknown`. A comparison scans every zone of `tzdata`,
so one file gets at most `MAX_COMPARISONS` of them (one per TZID and year); beyond, a
zone stays unknown.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from icalendar.timezone.windows_to_olson import WINDOWS_TO_OLSON

from app.modules.calendars import zones
from app.modules.calendars.ical import lines, problems
from app.modules.calendars.ical.problems import Skip
from app.modules.calendars.ical.vtimezone import Definition, definition
from app.modules.calendars.recurrence_rule import FIRST_YEAR, LAST_YEAR

MAX_COMPARISONS = 100
_NOON = 12
_WEEKS = 53


def by_name(tzid: str) -> str | None:
    """The IANA zone `tzid` names (steps 1 to 3), or None."""
    known = zones.names()
    cleaned = tzid.strip().strip("/")
    for candidate in (tzid, cleaned, WINDOWS_TO_OLSON.get(cleaned)):
        if candidate is not None and candidate in known:
            return candidate
    if tzid.strip().startswith("/"):
        parts = cleaned.split("/")
        for first in range(1, len(parts)):
            if (suffix := "/".join(parts[first:])) in known:
                return suffix
    return None


@lru_cache(maxsize=1)
def _ordered() -> tuple[tuple[str, ZoneInfo], ...]:
    known = zones.names()
    windows = sorted(set(WINDOWS_TO_OLSON.values()) & known)
    regional = sorted(n for n in known - set(windows) if "/" in n and not n.startswith("Etc/"))
    rest = sorted(known - set(windows) - set(regional))
    return tuple((name, ZoneInfo(name)) for name in (*windows, *regional, *rest))


def _samples(year: int) -> list[datetime]:
    first = datetime(year, 1, 1, _NOON)
    return [
        first + timedelta(weeks=week)
        for week in range(_WEEKS)
        if (first + timedelta(weeks=week)).year == year
    ]


class Resolver:
    """Resolves the TZIDs of one file; `timezones` are its VTIMEZONEs by TZID."""

    def __init__(self, timezones: Mapping[str, lines.Component]) -> None:
        self._components = dict(timezones)
        self._definitions: dict[str, Definition | None] = {}
        self._candidates: dict[tuple[str, int], list[str]] = {}

    def resolve(self, tzid: str, walls: Sequence[datetime]) -> str:
        """The zone of `tzid`, for an event with the wall times `walls` written in it
        (the first is its start); `Skip(ical.time_zone_unknown)` if none."""
        named = by_name(tzid)
        if named is not None:
            return named
        found = self._definition(tzid)
        if found is None or not walls:
            raise Skip(problems.TIME_ZONE_UNKNOWN)
        if not FIRST_YEAR <= walls[0].year <= LAST_YEAR:
            raise Skip(problems.TIME_OUT_OF_RANGE)
        expected = [(wall, found.offset_at(wall)) for wall in walls]
        for name in self._matching(tzid, found, walls[0].year):
            zone = ZoneInfo(name)
            if all(zone.utcoffset(wall) == offset for wall, offset in expected):
                return name
        raise Skip(problems.TIME_ZONE_UNKNOWN)

    def _definition(self, tzid: str) -> Definition | None:
        if tzid not in self._definitions:
            component = self._components.get(tzid)
            self._definitions[tzid] = definition(component) if component is not None else None
        return self._definitions[tzid]

    def _matching(self, tzid: str, found: Definition, year: int) -> list[str]:
        key = (tzid, year)
        if key not in self._candidates:
            if len(self._candidates) >= MAX_COMPARISONS:
                raise Skip(problems.TIME_ZONE_UNKNOWN)
            samples = [(s, found.offset_at(s)) for s in _samples(year)]
            ordered = list(_ordered())
            if found.location is not None and found.location in zones.names():
                ordered.insert(0, (found.location, ZoneInfo(found.location)))
            self._candidates[key] = [
                name
                for name, zone in ordered
                if all(zone.utcoffset(sample) == offset for sample, offset in samples)
            ]
        return self._candidates[key]
