"""The terms of a heartbeat (plan M7 decisions 5 and 7): pure functions, no database,
no clock of their own (the caller passes "now").

A heartbeat runs every `interval` minutes (15 to 1,440) inside its active hours:
weekdays (ISO, 1 = Monday) and a local time from–until in an IANA zone. A window
belongs to the weekday it opens on; one whose `until` is not after its `from` passes
midnight (22:00–06:00 on a Friday lasts into Saturday morning), and from = until is
the whole day. Windows that touch (whole days in a row) are one.

The next term is one interval after "now" while that is still inside the window
"now" is in; otherwise (the window closes first, or "now" is outside every window)
it is the next opening, but never less than one interval after "now" (the last
beat), also across a window's edge (review M7, finding 13). Outside the active hours
no term comes. Daylight saving time: an opening (or close) whose local time does not
exist that day falls to the next valid instant (02:30 → 03:00); one that exists twice
is the first; a window through a doubled hour lasts its real hours.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from app.modules.automations.terms import MIN_SPACING, TermError, zone

MIN_INTERVAL_MINUTES = int(MIN_SPACING.total_seconds() // 60)
MAX_INTERVAL_MINUTES = 24 * 60
WEEKDAYS = frozenset(range(1, 8))
_SCAN_DAYS = range(-1, 9)  # the window of yesterday may still be open; a week ahead
_MAX_GAP_MINUTES = 24 * 60  # local times a jump of the clocks skips


@dataclass(frozen=True, slots=True)
class Hours:
    days: frozenset[int]  # ISO weekdays, 1 = Monday
    start: time  # local, the opening
    end: time  # local; not after `start`: past midnight (equal: the whole day)
    time_zone: str


def check(interval: int, hours: Hours) -> tzinfo:
    """The zone, if the interval and the hours can be used (`TermError` otherwise)."""
    if interval < MIN_INTERVAL_MINUTES:
        raise TermError("automation.too_frequent")
    if interval > MAX_INTERVAL_MINUTES:
        raise TermError("automation.invalid_interval")
    if not hours.days or not hours.days <= WEEKDAYS:
        raise TermError("automation.invalid_hours")
    return zone(hours.time_zone)


def _instant(day: date, at: time, where: tzinfo) -> datetime:
    """The local `day` at `at` in UTC: the first of a doubled time, the next valid
    instant for one the clocks skip."""
    wall = datetime.combine(day, at)
    for minute in range(_MAX_GAP_MINUTES):
        local = (wall + timedelta(minutes=minute)).replace(tzinfo=where)
        found = local.astimezone(UTC)
        if found.astimezone(where).replace(tzinfo=None) == local.replace(tzinfo=None):
            return found
    raise TermError("automation.invalid_time_zone")  # no zone skips a whole day


def _windows(hours: Hours, where: tzinfo, around: datetime) -> list[tuple[datetime, datetime]]:
    """The open windows from yesterday to a week ahead of `around`, joined where they
    touch, in order (UTC)."""
    today = around.astimezone(where).date()
    over_midnight = hours.end <= hours.start
    found: list[tuple[datetime, datetime]] = []
    for offset in _SCAN_DAYS:
        day = today + timedelta(days=offset)
        if day.isoweekday() not in hours.days:
            continue
        opens = _instant(day, hours.start, where)
        closes = _instant(day + timedelta(days=int(over_midnight)), hours.end, where)
        if found and opens <= found[-1][1]:
            found[-1] = (found[-1][0], max(found[-1][1], closes))
        else:
            found.append((opens, closes))
    return found


def _aware(now: datetime) -> None:
    if now.tzinfo is None:
        raise ValueError("now must carry its time zone")


def inside(hours: Hours, at: datetime) -> bool:
    """Whether `at` (aware) is inside the active hours."""
    _aware(at)
    where = zone(hours.time_zone)
    return any(opens <= at < closes for opens, closes in _windows(hours, where, at))


def next_heartbeat(interval: int, hours: Hours, now: datetime) -> datetime:
    """The heartbeat's next term after `now` (aware), in UTC."""
    _aware(now)
    where = check(interval, hours)
    step = timedelta(minutes=interval)
    soonest = now + step  # never closer to the last beat than the interval
    for opens, closes in _windows(hours, where, now):
        candidate = max(opens, soonest)
        if closes > now and candidate < closes:
            return candidate
    raise TermError("automation.invalid_hours")  # a weekday comes within a week
