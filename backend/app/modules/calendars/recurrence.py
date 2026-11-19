"""Series and their occurrences (plan M10 decision 6): pure, no database. The rule's
matches come from `recurrence_scan`, the one module that talks to `dateutil`
(`tests/test_calendar_imports.py` allows it there and in `recurrence_jump`, which
needs none so far).

- A series is expanded in the **wall time of its zone** (naive `datetime`s) and each
  occurrence localised afterwards (`zones.localise`: a gap moves on, a doubled hour
  takes the first). `start`, `rdates`, `exdates` and every `recurrence_id` are wall
  times, so a deleted or moved occurrence keeps matching when `tzdata` changes a zone's
  offsets. All-day series float on 00:00 UTC (no `tzid`).
- DTSTART is always the first occurrence, and `COUNT` counts it (RFC 5545 3.8.5.3).
  `UNTIL` is an instant for a start with a zone and a date for an all-day one; it is
  compared as such. RDATEs add, EXDATEs remove (by wall time); a duplicate is one.
- Occurrences overlap the window `[window_from, window_to)`; more than `limit` raise
  `TooDense`. An endless rule jumps to the window (`recurrence_jump`), a counted one
  too where its count per period is fixed (`counted_jump`, `recurrence_count`). Two occurrences
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
  sparse rule still scans to its next match on each call, bounded by the horizon
  (`recurrence_scan`).
"""

import heapq
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime, time, timedelta
from itertools import chain, islice

from app.modules.calendars.recurrence_jump import Counter, counted_jump, jump
from app.modules.calendars.recurrence_rule import (
    FIRST_YEAR,
    LAST_YEAR,
    ParsedRule,
    RuleInvalid,
    SeriesInvalid,
    check_rule,
)
from app.modules.calendars.recurrence_scan import HORIZON, matches
from app.modules.calendars.recurrence_series import (
    Occurrence,
    Series,
    as_wall,
    bounded,
    instant,
    shift,
    wall_of,
)

__all__ = [
    "FIRST_YEAR",
    "HORIZON",
    "LAST_YEAR",
    "Occurrence",
    "RuleInvalid",
    "Series",
    "SeriesInvalid",
    "TooDense",
    "check_rule",
    "recurrence_id_at",
    "shift",
]

DEFAULT_LIMIT = 2000
LAST_END_CAP = 5000
# Offsets of one zone differ by up to a day (Pacific/Apia skipped 30 December 2011).
SLACK = timedelta(hours=26)


class TooDense(Exception):
    code = "calendar.window_too_dense"


def _last_instant(series: Series, rule: ParsedRule) -> datetime | None:
    if isinstance(rule.until, datetime):
        return rule.until
    if isinstance(rule.until, date):
        return datetime.combine(rule.until, time(), tzinfo=UTC)
    return None


def rule_walls(
    series: Series, lo: datetime, stop: datetime, counter: Counter
) -> Iterator[datetime]:
    """DTSTART, then the rule's matches (`COUNT` and `UNTIL` applied), in order; from
    `lo` on (earlier ones may come too) and up to around `stop`."""
    start, rule = series.start, series.rule
    if rule is None:
        yield start
        return
    begin, done = jump(rule, start, lo), 0
    counted = counted_jump(rule, start, lo, lambda until: _between(rule, start, until, counter))
    if counted is not None:  # `done`: the occurrences before `begin`, DTSTART included
        begin, done = counted
    counter.jumps += begin != start
    last = _last_instant(series, rule)
    if last is not None:
        stop = min(stop, wall_of(series, last) + SLACK)
    ruled = (
        wall
        for wall in matches(rule, start, begin, stop, counter)
        if wall != start and (last is None or instant(series, wall) <= last)
    )
    ordered = chain([start] if begin == start else [], ruled)
    yield from islice(ordered, max(rule.count - done, 0)) if rule.count is not None else ordered


def _between(rule: ParsedRule, start: datetime, stop: datetime, counter: Counter) -> int:
    """The rule's matches after DTSTART and before `stop`."""
    return sum(start < wall < stop for wall in matches(rule, start, start, stop, counter))


def walls(
    series: Series,
    lo: datetime,
    hi: datetime,
    counter: Counter,
    *,
    keep_exdates: bool = False,
    rdates: Sequence[datetime] | None = None,
) -> Iterator[datetime]:
    """Every occurrence's wall time from `lo` to `hi` (inclusive), in order, once
    (`keep_exdates`: deleted ones too; `rdates`: the series' RDATEs from `lo` on,
    sorted, once: `recurrence_ids` asks for many ids at once)."""
    if rdates is None:
        rdates = sorted(wall for wall in set(series.rdates) if wall >= lo)
    exdates = frozenset(() if keep_exdates else series.exdates)
    previous = None
    for wall in heapq.merge(rule_walls(series, lo, hi, counter), rdates):
        if wall > hi:
            return
        if wall != previous and wall >= lo and wall not in exdates:
            yield wall
        previous = wall


def check_series(series: Series) -> datetime | None:
    """Refuses a rule that never matches (`event.rrule_invalid`): its every expansion
    would scan to the horizon. Every path that writes a series calls it (Tasks 3a, 3b,
    7b, 13b). Returns the rule's first match (how far the check scanned)."""
    rule = series.rule
    if rule is None:
        return None
    first = next(matches(rule, series.start, series.start, HORIZON, Counter()), None)
    if first is None:
        raise RuleInvalid("event.rrule_invalid")
    return first


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
    for found in rule_walls(series, series.start, wall, Counter()):
        if found >= wall:
            break
        count += 1
    return count
