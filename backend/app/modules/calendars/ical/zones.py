"""Which IANA zone a file's TZID means (plan M10 decision 10), per file and never
through `icalendar`'s process-wide zone cache:

1. an IANA name (also with the slashes some producers put around it);
2. the library's table of Windows names (`W. Europe Standard Time` → `Europe/Berlin`);
3. the Olson name at the end of a "globally unique" TZID
   (`/mozilla.org/20050126_1/America/New_York`, RFC 5545 3.2.19);
4. the file's VTIMEZONE compared with `tzdata` (R7a-10). A zone fits a year when it
   has the definition's offset from UTC at noon of every week of it; the years
   compared are the start's and a few more across the years the event spans
   (`years`), so a series that began before today's rules still finds its zone. Of the
   zones that fit and have the definition's offset at the event's own times, the one
   wins that fits the most of those years, then one the definition names (its
   `X-LIC-LOCATION`, or a city the TZID names), then the table's Windows zones (one
   well-known city per region) before other regional zones before the rest (`Etc/…`,
   `CET`), then the one that has followed the definition in the most weeks of
   `REFERENCE_YEARS` (US Eastern rules: `America/New_York`, not `Grand_Turk`), then
   by name: the same choice every time.

A TZID longer than `MAX_TZID` characters or of more than `MAX_TZID_SEGMENTS` parts is
never looked up (`ical.time_zone_too_large`, re-check RC7a-3): an IANA name has at most
three parts, so only the last three of a globally unique TZID are tried.

Nothing fits: `ical.time_zone_unknown`. A comparison scans every zone of `tzdata`,
so one file gets at most `MAX_COMPARISONS` of them (one per TZID and year); beyond, a
zone stays unknown. Every comparison is charged to the parse's budget.
"""

import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from icalendar.timezone.windows_to_olson import WINDOWS_TO_OLSON

from app.modules.calendars import zones
from app.modules.calendars.ical import lines, problems
from app.modules.calendars.ical.budget import Budget, offset_cost
from app.modules.calendars.ical.problems import Skip
from app.modules.calendars.ical.vtimezone import Definition, definition
from app.modules.calendars.recurrence_rule import FIRST_YEAR, LAST_YEAR

MAX_COMPARISONS = 100
# The longest IANA name has 32 characters and three parts; producers put a prefix of
# two or three more before it (`/mozilla.org/20050126_1/America/New_York`).
MAX_TZID = 255
MAX_TZID_SEGMENTS = 8
_IANA_PARTS = 3
MAX_YEARS = 6  # years compared for one event
# Years after these follow `tzdata`'s last rule (and a definition's), so later ones
# tell nothing new.
LAST_COMPARED_YEAR = 2040
# Since 1981 Europe's and since 1987 the United States' changes follow today's pattern:
# the zones that have followed a definition longest within these years are the ones
# meant (measured: Europe → Berlin among Budapest, Paris, Warsaw; US Eastern → New York).
REFERENCE_YEARS = range(1981, 2038)
_NOON = 12
_WEEKS = 53
# Areas whose names are a city, never a link kept for old names (`US/Eastern`).
_AREAS = frozenset(
    {"Africa", "America", "Antarctica", "Arctic", "Asia", "Atlantic", "Australia"}
    | {"Europe", "Indian", "Pacific"}
)
_NOT_LETTERS = re.compile(r"[^a-z]+")


def too_large(tzid: str) -> bool:
    """Whether `tzid` is beyond `MAX_TZID` characters or `MAX_TZID_SEGMENTS` parts."""
    return len(tzid) > MAX_TZID or tzid.strip().strip("/").count("/") >= MAX_TZID_SEGMENTS


def _free(units: int) -> None:
    pass


def by_name(tzid: str, spend: Callable[[int], None] = _free) -> str | None:
    """The IANA zone `tzid` names (steps 1 to 3), or None; one unit per name looked up
    goes to `spend`."""
    if too_large(tzid):
        return None
    known = zones.names()
    cleaned = tzid.strip().strip("/")
    spend(3)
    for candidate in (tzid, cleaned, WINDOWS_TO_OLSON.get(cleaned)):
        if candidate is not None and candidate in known:
            return candidate
    if tzid.strip().startswith("/"):
        parts = cleaned.split("/")
        for size in range(min(_IANA_PARTS, len(parts) - 1), 0, -1):
            spend(1)
            if (suffix := "/".join(parts[-size:])) in known:
                return suffix
    return None


def years(first: int, last: int) -> tuple[int, ...]:
    """The years compared for an event that spans `first` to `last`: the first, then at
    most `MAX_YEARS - 1` of every tenth year and the last (up to
    `LAST_COMPARED_YEAR`), spread evenly; on a fixed grid, so events share them."""
    last = min(last, LAST_COMPARED_YEAR)
    later = [y for y in range(first - first % 10 + 10, last, 10)]
    if last > first:
        later.append(last)
    room = MAX_YEARS - 1
    if len(later) > room:
        later = [later[i * (len(later) - 1) // (room - 1)] for i in range(room)]
    return (first, *later)


@lru_cache(maxsize=1)
def _ranks() -> dict[str, tuple[int, int]]:
    """Every zone's group (0: the table's Windows zones, 1: other regional zones, 2: the
    rest) and its place in the order of trial."""
    known = zones.names()
    windows = sorted(set(WINDOWS_TO_OLSON.values()) & known)
    regional = sorted(n for n in known - set(windows) if "/" in n and not n.startswith("Etc/"))
    rest = sorted(known - set(windows) - set(regional))
    groups = ((0, windows), (1, regional), (2, rest))
    ordered = [(group, name) for group, names in groups for name in names]
    return {name: (group, index) for index, (group, name) in enumerate(ordered)}


@lru_cache(maxsize=1)
def _zones() -> tuple[tuple[str, ZoneInfo], ...]:
    ranks = _ranks()
    return tuple((name, ZoneInfo(name)) for name in sorted(ranks, key=lambda n: ranks[n][1]))


def _samples(year: int) -> list[datetime]:
    first = datetime(year, 1, 1, _NOON)
    return [
        first + timedelta(weeks=week)
        for week in range(_WEEKS)
        if (first + timedelta(weeks=week)).year == year
    ]


def _named(tzid: str, found: Definition, name: str) -> bool:
    """Whether the definition names the zone: its `X-LIC-LOCATION`, or the city in the
    TZID (`(UTC+01:00) Amsterdam, Berlin, …`)."""
    if name == found.location:
        return True
    area, _, city = name.rpartition("/")
    if area.split("/")[0] not in _AREAS:
        return False
    words = f" {_NOT_LETTERS.sub(' ', tzid.lower()).strip()} "
    return f" {_NOT_LETTERS.sub(' ', city.lower()).strip()} " in words


class Resolver:
    """Resolves the TZIDs of one file; `timezones` are its VTIMEZONEs by TZID."""

    def __init__(self, timezones: Mapping[str, lines.Component]) -> None:
        self._components = dict(timezones)
        self._definitions: dict[str, Definition | None] = {}
        self._candidates: dict[tuple[str, int], list[str]] = {}
        self._same: dict[Definition, Definition] = {}  # one instance per content
        self._references: dict[tuple[int, str], int] = {}
        self._reference_offsets: dict[int, list[tuple[datetime, timedelta]]] = {}

    def resolve(
        self, tzid: str, walls: Sequence[datetime], compared: Sequence[int], budget: Budget
    ) -> str:
        """The zone of `tzid`, for an event with the wall times `walls` written in it
        (the first is its start) that spans the years `compared` (the first is its
        start's); `Skip(ical.time_zone_unknown)` if none. The work is charged to
        `budget`."""
        if too_large(tzid):
            raise Skip(problems.TIME_ZONE_TOO_LARGE)
        named = by_name(tzid, budget.spend)
        if named is not None:
            return named
        found = self._definition(tzid)
        if found is None or not walls:
            raise Skip(problems.TIME_ZONE_UNKNOWN)
        if not FIRST_YEAR <= walls[0].year <= LAST_YEAR:
            raise Skip(problems.TIME_OUT_OF_RANGE)
        budget.spend(len(walls) * offset_cost(found.ruled))
        expected = [(wall, found.offset_at(wall)) for wall in walls]
        fits: Counter[str] = Counter()
        for index, year in enumerate(compared or (walls[0].year,)):
            try:
                fits.update(self._matching(tzid, found, year, budget))
            except Skip:
                if index == 0:
                    raise
                break  # no more comparisons for this file: decide on what was compared
        for name in self._ranked(tzid, found, fits, budget):
            budget.spend(1 + len(expected) // 4)
            zone = ZoneInfo(name)
            if all(zone.utcoffset(wall) == offset for wall, offset in expected):
                return name
        raise Skip(problems.TIME_ZONE_UNKNOWN)

    def _definition(self, tzid: str) -> Definition | None:
        if tzid not in self._definitions:
            component = self._components.get(tzid)
            found = definition(component) if component is not None else None
            if found is not None:
                found = self._same.setdefault(found, found)
            self._definitions[tzid] = found
        return self._definitions[tzid]

    def _matching(self, tzid: str, found: Definition, year: int, budget: Budget) -> list[str]:
        key = (tzid, year)
        if key not in self._candidates:
            if len(self._candidates) >= MAX_COMPARISONS:
                raise Skip(problems.TIME_ZONE_UNKNOWN)
            budget.spend(_WEEKS * offset_cost(found.ruled))
            samples = [(s, found.offset_at(s)) for s in _samples(year)]
            looked, matching = _fitting(samples, _zones())
            budget.spend(looked // 4)
            self._candidates[key] = matching
        return self._candidates[key]

    def _ranked(
        self, tzid: str, found: Definition, fits: Counter[str], budget: Budget
    ) -> list[str]:
        ranks = _ranks()

        def first_keys(name: str) -> tuple[int, bool, int]:
            return (-fits[name], not _named(tzid, found, name), ranks[name][0])

        ranked = sorted(fits, key=lambda name: (first_keys(name), ranks[name][1]))
        lead = [name for name in ranked if first_keys(name) == first_keys(ranked[0])]
        if len(lead) > 1:
            scores = {name: self._reference(found, name, budget) for name in lead}
            lead.sort(key=lambda name: (-scores[name], ranks[name][1]))
            ranked[: len(lead)] = lead
        return ranked

    def _reference(self, found: Definition, name: str, budget: Budget) -> int:
        """In how many weeks of `REFERENCE_YEARS` the zone `name` had the definition's
        offset (cached per definition, so many TZIDs of one definition pay once;
        `_same` keeps one instance per content, kept alive by the resolver)."""
        if id(found) not in self._reference_offsets:
            samples = [s for year in REFERENCE_YEARS for s in _samples(year)]
            budget.spend(len(samples) * offset_cost(found.ruled))
            self._reference_offsets[id(found)] = [(s, found.offset_at(s)) for s in samples]
        key = (id(found), name)
        if key not in self._references:
            offsets = self._reference_offsets[id(found)]
            budget.spend(len(offsets) // 4)
            zone = ZoneInfo(name)
            self._references[key] = sum(zone.utcoffset(s) == offset for s, offset in offsets)
        return self._references[key]


def _fitting(
    samples: list[tuple[datetime, timedelta]], candidates: Sequence[tuple[str, ZoneInfo]]
) -> tuple[int, list[str]]:
    """The zones that have every sample's offset, and how many offsets were looked up."""
    looked = 0
    matching = []
    for name, zone in candidates:
        for sample, offset in samples:
            looked += 1
            if zone.utcoffset(sample) != offset:
                break
        else:
            matching.append(name)
    return looked, matching
