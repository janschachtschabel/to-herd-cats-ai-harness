"""Series and their occurrences (plan M10 decision 6): pure, no database. The module
that imports `dateutil` (`tests/test_calendar_imports.py` allows it here and in
`recurrence_jump`, which needs none so far).

- A series is expanded in the **wall time of its zone** (naive `datetime`s) and each
  occurrence localised afterwards (`zones.localise`: a gap moves on, a doubled hour
  takes the first). `start`, `rdates`, `exdates` and every `recurrence_id` are wall
  times, so a deleted or moved occurrence keeps matching when `tzdata` changes a zone's
  offsets. All-day series float on 00:00 UTC (no `tzid`).
- DTSTART is always the first occurrence, and `COUNT` counts it (RFC 5545 3.8.5.3).
  `UNTIL` is an instant for a start with a zone and a date for an all-day one; it is
  compared as such. RDATEs add, EXDATEs remove (by wall time); a duplicate is one.
- Occurrences overlap the window `[window_from, window_to)`; more than `limit` raise
  `TooDense`. An endless rule jumps to the window (`recurrence_jump`). Two occurrences
  that start at one instant (a gap's moved wall time where the next one is: Pacific/Apia
  on 30 December 2011, or an RDATE beside it) show once, by the earlier recurrence id.
  An occurrence in a gap keeps the wall time the rule names as its id (RFC 5545
  RECURRENCE-ID); `recurrence_id_at` finds it from the instant it starts at.
- Bounded work: series lie in the years 1900 to 2399 (`recurrence_series`: windows and
  instants beyond them are moved to them). `dateutil` scans periods without a
  candidate until its `MAXYEAR`, so it runs 7,600 years (19 Gregorian cycles, the same
  weekdays and leap years) ahead of us, where its `MAXYEAR` 9999 is our 2399.
  `check_series` refuses a rule that never matches (it would scan on every call):
  **every write path calls it** (create, update, split, import, sync); an alive but
  sparse rule still scans to its next match on each call, bounded by the horizon.
"""

import heapq
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from itertools import chain, islice
from typing import Any

from dateutil.rrule import DAILY, MONTHLY, WEEKLY, YEARLY, rrule, weekday

from app.modules.calendars.recurrence_jump import Counter, jump, week_start
from app.modules.calendars.recurrence_rule import (
    FIRST_YEAR,
    LAST_YEAR,
    Freq,
    ParsedRule,
    RuleInvalid,
    SeriesInvalid,
    check_rule,
)
from app.modules.calendars.recurrence_series import (
    Occurrence,
    Series,
    as_wall,
    bounded,
    instant,
    wall_of,
)

__all__ = [
    "FIRST_YEAR",
    "LAST_YEAR",
    "Occurrence",
    "RuleInvalid",
    "Series",
    "SeriesInvalid",
    "TooDense",
    "check_rule",
    "recurrence_id_at",
]

DEFAULT_LIMIT = 2000
LAST_END_CAP = 5000
HORIZON = datetime(LAST_YEAR, 12, 31, 23, 59, 59)
_AHEAD_YEARS = 7600
# Offsets of one zone differ by up to a day (Pacific/Apia skipped 30 December 2011).
SLACK = timedelta(hours=26)
_FREQS = {Freq.DAILY: DAILY, Freq.WEEKLY: WEEKLY, Freq.MONTHLY: MONTHLY, Freq.YEARLY: YEARLY}


class TooDense(Exception):
    code = "calendar.window_too_dense"


def _ahead(wall: datetime) -> datetime:
    return wall.replace(year=wall.year + _AHEAD_YEARS)


def _byweekday(rule: ParsedRule) -> list[weekday]:
    """BYDAY as `dateutil` takes it. RFC 5545 reads BYDAY as one list, but `dateutil`
    keeps plain and numbered days as two filters that must both hold; where a rule
    mixes them, each plain day becomes all its numbered ones (within the month, or the
    year of a YEARLY rule without BYMONTH), which is the same set of days."""
    numbered = [weekday(day, n) for day, n in rule.byday if n]
    plain = [day for day, n in rule.byday if not n]
    if not (numbered and plain):
        return numbered or [weekday(day) for day in plain]
    top = 53 if rule.freq is Freq.YEARLY and not rule.bymonth else 5
    return numbered + [weekday(day, n) for day in plain for n in range(1, top + 1)]


def _kwargs(rule: ParsedRule, start: datetime) -> dict[str, Any]:
    """`dateutil`'s arguments with the defaults taken from the original start, so the
    rule can run from a jumped one."""
    byweekday = _byweekday(rule)
    bymonth, bymonthday = list(rule.bymonth), list(rule.bymonthday)
    if not (bymonthday or byweekday):
        if rule.freq is Freq.YEARLY:
            bymonth, bymonthday = bymonth or [start.month], [start.day]
        elif rule.freq is Freq.MONTHLY:
            bymonthday = [start.day]
        elif rule.freq is Freq.WEEKLY:
            byweekday = [weekday(start.weekday())]
    return {
        "freq": _FREQS[rule.freq],
        "interval": rule.interval,
        "wkst": rule.wkst,
        "bymonth": bymonth or None,
        "bymonthday": bymonthday or None,
        "byweekday": byweekday or None,
        "bysetpos": list(rule.bysetpos) or None,
        "byhour": start.hour,
        "byminute": start.minute,
        "bysecond": start.second,
    }


def _matches(
    rule: ParsedRule, start: datetime, begin: datetime, stop: datetime, counter: Counter
) -> Iterator[datetime]:
    """The rule's matches from `begin` on, in order, until one lies past `stop`."""
    if begin > HORIZON:
        return
    first = begin
    if rule.freq is Freq.WEEKLY and rule.bysetpos:
        # `dateutil` builds a weekly period's set from DTSTART's day on, so BYSETPOS
        # would count in a cut first week; run it from the week's start (WKST) and drop
        # what lies before `begin` (RFC 5545 3.3.10: the whole set, then >= DTSTART).
        first = datetime.combine(week_start(begin.date(), rule.wkst), begin.time())
    until = _ahead(min(stop, HORIZON))
    run = rrule(dtstart=_ahead(first), until=until, cache=False, **_kwargs(rule, start))
    for found in run:
        counter.candidates += 1
        wall = found.replace(year=found.year - _AHEAD_YEARS)
        if wall >= begin:
            yield wall


def _last_instant(series: Series, rule: ParsedRule) -> datetime | None:
    if isinstance(rule.until, datetime):
        return rule.until
    if isinstance(rule.until, date):
        return datetime.combine(rule.until, time(), tzinfo=UTC)
    return None


def _rule_walls(
    series: Series, lo: datetime, stop: datetime, counter: Counter
) -> Iterator[datetime]:
    """DTSTART, then the rule's matches (`COUNT` and `UNTIL` applied), in order; from
    `lo` on (earlier ones may come too) and up to around `stop`."""
    start, rule = series.start, series.rule
    if rule is None:
        yield start
        return
    begin = jump(rule, start, lo)
    counter.jumps += begin != start
    last = _last_instant(series, rule)
    if last is not None:
        stop = min(stop, wall_of(series, last) + SLACK)
    matches = (
        wall
        for wall in _matches(rule, start, begin, stop, counter)
        if wall != start and (last is None or instant(series, wall) <= last)
    )
    every = chain([start] if begin == start else [], matches)
    yield from islice(every, rule.count) if rule.count is not None else every


def walls(
    series: Series, lo: datetime, hi: datetime, counter: Counter, *, keep_exdates: bool = False
) -> Iterator[datetime]:
    """Every occurrence's wall time from `lo` to `hi` (inclusive), in order, once."""
    rdates = sorted(wall for wall in set(series.rdates) if wall >= lo)
    exdates = frozenset(() if keep_exdates else series.exdates)
    previous = None
    for wall in heapq.merge(_rule_walls(series, lo, hi, counter), rdates):
        if wall > hi:
            return
        if wall != previous and wall >= lo and wall not in exdates:
            yield wall
        previous = wall


def check_series(series: Series) -> None:
    """Refuses a rule that never matches (`event.rrule_invalid`): its every expansion
    would scan to the horizon. Every path that writes a series calls it (Tasks 3a, 3b,
    7b, 13b); reading never does."""
    rule = series.rule
    if rule is not None:
        found = _matches(rule, series.start, series.start, HORIZON, Counter())
        if next(found, None) is None:
            raise RuleInvalid("event.rrule_invalid")


def occurrences(
    series: Series,
    window_from: datetime,
    window_to: datetime,
    *,
    limit: int = DEFAULT_LIMIT,
    counter: Counter | None = None,
) -> list[Occurrence]:
    """The occurrences overlapping `[window_from, window_to)`, by start; `TooDense`
    beyond `limit`. Two that start at one instant (a gap's moved wall time where another
    one is) show once, by the earlier recurrence id."""
    counter = counter if counter is not None else Counter()
    window_from, window_to = bounded(window_from), bounded(window_to)
    lo = wall_of(series, window_from - series.duration) - SLACK
    hi = min(wall_of(series, window_to) + SLACK, HORIZON)
    found: dict[datetime, Occurrence] = {}
    for wall in walls(series, lo, hi, counter):
        start = instant(series, wall)
        end = start + series.duration
        in_window = start < window_to and (end > window_from or end == start >= window_from)
        if in_window and start not in found:  # walls come in order: the earlier id stays
            found[start] = Occurrence(start, end, wall)
            if len(found) > limit:
                raise TooDense
    return sorted(found.values(), key=lambda o: (o.start, o.recurrence_id))


def next_after(series: Series, after: datetime) -> Occurrence | None:
    """The first occurrence that starts after `after` (deleted ones skipped; of two at
    one instant the earlier recurrence id)."""
    after = bounded(after)
    best: Occurrence | None = None
    for wall in walls(series, wall_of(series, after) - SLACK, HORIZON, Counter()):
        if best is not None and wall > best.recurrence_id + 2 * SLACK:
            break
        start = instant(series, wall)
        if start > after and (best is None or start < best.start):
            best = Occurrence(start, start + series.duration, wall)
    return best


def last_end(series: Series, *, cap: int = LAST_END_CAP) -> datetime | None:
    """When the series' last occurrence ends; None if it is endless or has more than
    `cap` occurrences (besides its RDATEs)."""
    rule = series.rule
    if rule is not None and rule.count is None and rule.until is None:
        return None
    lo = min((series.start, *series.rdates))
    ends = []
    for number, wall in enumerate(walls(series, lo, HORIZON, Counter()), start=1):
        if rule is not None and number > cap + len(series.rdates):
            return None
        ends.append(instant(series, wall) + series.duration)
    return max(ends, default=instant(series, series.start) + series.duration)


def is_occurrence(series: Series, recurrence_id: datetime) -> bool:
    """Whether the series names an occurrence `recurrence_id` (deleted ones too); an
    aware id is read as the series' wall time of that instant."""
    wall = as_wall(series, recurrence_id)
    named = walls(series, wall, wall, Counter(), keep_exdates=True)
    return any(found == wall for found in named)


def recurrence_id_at(series: Series, moment: datetime) -> datetime | None:
    """The recurrence id of the occurrence (deleted ones too) that starts at the instant
    `moment`, or None: the wall time the series names it by, which for an occurrence
    in a gap is not the wall time of its start. Of two at one instant, the earlier."""
    if bounded(moment) != moment:
        return None
    wall = wall_of(series, moment)
    near = walls(series, wall - SLACK, wall + SLACK, Counter(), keep_exdates=True)
    return next((found for found in near if instant(series, found) == moment), None)


def count_before(series: Series, recurrence_id: datetime) -> int:
    """How many of the series' counted occurrences (DTSTART and the rule's, deleted
    ones too, not RDATEs) come before `recurrence_id` (an aware one read as a wall
    time): what splitting a counted series there leaves to its first part."""
    wall = as_wall(series, recurrence_id)
    count = 0
    for found in _rule_walls(series, series.start, wall, Counter()):
        if found >= wall:
            break
        count += 1
    return count


def shift(wall: datetime, delta: timedelta) -> datetime:
    """The wall time `delta` later, by the clock on the wall (`event.time_out_of_range`
    beyond `datetime`'s years)."""
    if wall.tzinfo is not None:
        raise ValueError("a wall time is naive")
    try:
        return wall + delta
    except OverflowError:
        raise SeriesInvalid("event.time_out_of_range") from None
