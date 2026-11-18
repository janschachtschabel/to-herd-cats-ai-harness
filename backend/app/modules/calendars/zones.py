"""Time zones of the calendar (plan M10 decision 6): pure, IANA names from `tzdata`
only, never the process's zone.

A wall time is a naive `datetime` read in a zone. `localise` turns it into an instant
by RFC 5545 3.3.5: a wall time that does not exist that day (02:30 when the clocks
jump from 02:00 to 03:00) moves on by the gap (to 03:30); one that exists twice (02:30
when they fall back) is the first of the two. That is PEP 495's `fold=0`, which
`zoneinfo` implements. All-day events float: they lie on 00:00 UTC of their days.
"""

from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

# Files of the system's zone directory that are no IANA zone of their own.
_NOT_ZONES = frozenset({"localtime", "posixrules", "Factory"})


class ZoneUnknown(ValueError):
    """`tzid` is no IANA zone name."""


@lru_cache(maxsize=1)
def _zone_names() -> frozenset[str]:
    return frozenset(available_timezones()) - _NOT_ZONES


def zone(tzid: str) -> ZoneInfo:
    if tzid not in _zone_names():
        raise ZoneUnknown(tzid)
    return ZoneInfo(tzid)


def localise(wall: datetime, tzid: str) -> datetime:
    """The instant (UTC) of the wall time `wall` in `tzid`."""
    if wall.tzinfo is not None:
        raise ValueError("a wall time is naive")
    return wall.replace(tzinfo=zone(tzid), fold=0).astimezone(UTC)


def wall(instant: datetime, tzid: str) -> datetime:
    """The wall time of the instant `instant` in `tzid` (naive)."""
    if instant.tzinfo is None:
        raise ValueError("an instant is aware")
    return instant.astimezone(zone(tzid)).replace(tzinfo=None, fold=0)


def all_day_bounds(first: date, last: date) -> tuple[datetime, datetime]:
    """Start and end of all-day days `first` to `last`: 00:00 UTC of the first and of
    the day after the last."""
    if last < first:
        raise ValueError("the last day lies before the first")
    begin = datetime.combine(first, time(), tzinfo=UTC)
    return begin, datetime.combine(last, time(), tzinfo=UTC) + timedelta(days=1)
