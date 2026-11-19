"""How close a series' occurrences come to each other (review M10 task 3a, R3a-1):
pure, on `recurrence.walls`.

A series whose occurrences last longer than the shortest gap between two consecutive
ones lies on top of itself; a daily one lasting six years runs 2,191 times at every
instant and closes every window that reaches its calendar. Every write path refuses it
(`event_times.check`, `event.series_overlaps`).

- The gap is read on the series' wall clock (its zone's), so a daily 24-hour shift
  stays allowed across a clock change; its occurrences then overlap by the hour the
  clocks skip, twice a year at most, which no window notices.
- Deleted occurrences (EXDATEs) count as occurrences: deleting one does not let its
  neighbours grow into its place, and restoring it needs no second check.
- Bounded work: a counted series and one without a rule have at most 5,500
  occurrences (`COUNT` ≤ 5,000, 500 RDATEs) and are read whole. An endless one, or
  one with `UNTIL`, is read for its first `GAP_SAMPLE` occurrences, and every later
  RDATE among its neighbours (the rule jumps there, `recurrence_jump`). A rule's
  pattern repeats within its period, so a gap first met beyond the sample is a rare
  calendar coincidence (a leap day, a fifth weekday) that lets two occurrences touch
  at most.
"""

from collections.abc import Iterable
from datetime import datetime, timedelta
from itertools import islice, pairwise

from app.modules.calendars.recurrence import HORIZON, SLACK, Series, walls
from app.modules.calendars.recurrence_jump import Counter

GAP_SAMPLE = 1000


def _shortest(found: Iterable[datetime]) -> timedelta | None:
    return min((b - a for a, b in pairwise(found)), default=None)


def shortest_gap(series: Series) -> timedelta | None:
    """The shortest wall-clock gap between two consecutive occurrences of the series
    (deleted ones included); None for a series of one."""
    rule = series.rule
    every = walls(series, series.start, HORIZON, Counter(), keep_exdates=True)
    if rule is None or rule.count is not None:
        return _shortest(every)
    sample = list(islice(every, GAP_SAMPLE))
    gaps = [_shortest(sample)]
    if len(sample) == GAP_SAMPLE:
        reach = series.duration + SLACK
        for rdate in sorted(set(series.rdates)):
            if rdate > sample[-1]:
                near = walls(series, rdate - reach, rdate + reach, Counter(), keep_exdates=True)
                gaps.append(_shortest(near))
    return min((gap for gap in gaps if gap is not None), default=None)


def overlaps_itself(series: Series) -> bool:
    """Whether an occurrence of the series lasts past the start of the next one."""
    gap = shortest_gap(series)
    return gap is not None and series.duration > gap
