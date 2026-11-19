"""Many recurrence ids of one series at once (review M10 Task 7a, R7a-4 and R7a-6): what
`recurrence.is_occurrence` and `recurrence.recurrence_id_at` answer for each of many
values, at the cost of one expansion per stretch of them instead of one per value.

The series is expanded over each cluster of values (values closer than `CLUSTER`
share a pass), each pass jumping to its cluster, with the series' RDATEs sorted once
and cut per pass (re-check RC7a-4). A counted rule counts from its start: each cluster
is first matched against the rule without its COUNT (the same walls and more), and the
counted rule is run from its start only as far as a match found there, never past its
COUNT-th (re-check RC7a-2): a value the rule cannot name costs its own cluster only.

`spend` is told of the work as it is done (`recurrence_cost`): before a pass its first
period and its RDATEs, at each wall time the periods scanned since the one before and
the wall time, after it the periods scanned past its end to the candidate that ended
the scan (or to the horizon); it may stop the work by raising.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import replace
from datetime import datetime, timedelta

from app.modules.calendars import recurrence_cost
from app.modules.calendars.recurrence import HORIZON, SLACK, walls
from app.modules.calendars.recurrence_jump import Counter
from app.modules.calendars.recurrence_rule import ParsedRule
from app.modules.calendars.recurrence_series import Series, bounded, instant, wall_of

CLUSTER = timedelta(days=31)
Spend = Callable[[int], None]


def named(series: Series, values: Iterable[datetime], spend: Spend) -> frozenset[datetime]:
    """Which of the wall times `values` the series names as occurrences, deleted ones
    too (`is_occurrence` for each)."""
    wanted = frozenset(values)
    ordered = sorted(wanted)
    found = _walls_over(series, ordered, ordered, spend)
    return frozenset(wall for wall in found if wall in wanted)


def ids_at(series: Series, moments: Iterable[datetime], spend: Spend) -> dict[datetime, datetime]:
    """The recurrence id of the occurrence (deleted ones too) that starts at each
    instant of `moments` that has one; of two at one instant the earlier
    (`recurrence_id_at` for each)."""
    wanted = frozenset(m for m in moments if bounded(m) == m)
    centres = sorted(wall_of(series, m) for m in wanted)
    found: dict[datetime, datetime] = {}
    spans = ([c - SLACK for c in centres], [c + SLACK for c in centres])
    for wall in _walls_over(series, *spans, spend):
        moment = instant(series, wall)
        if moment in wanted and moment not in found:
            found[moment] = wall
    return found


def _walls_over(
    series: Series, los: list[datetime], his: list[datetime], spend: Spend
) -> list[datetime]:
    """The series' wall times (deleted ones too) over the spans `[los[i], his[i]]`
    (both sorted), in order and once."""
    if not los:
        return []
    spend(len(series.rdates))
    rdates = sorted(set(series.rdates))
    rule = series.rule
    if rule is None or rule.count is None:
        return list(_passes(series, rule, los, his, rdates, spend))
    return list(_counted_passes(series, rule, los, his, rdates, spend))


def _counted_passes(
    series: Series,
    rule: ParsedRule,
    los: list[datetime],
    his: list[datetime],
    rdates: list[datetime],
    spend: Spend,
) -> Iterator[datetime]:
    """A counted rule's wall times over the spans: each span is matched against the rule
    without its COUNT, and a match is kept if the counted rule, run from its start as
    far as that match (and never past its COUNT-th), has it too. Once the counted rule
    has ended, a span holds only its start and RDATEs."""
    uncounted = replace(rule, count=None)
    pattern = replace(series, rrule=uncounted.text, rdates=(), exdates=())
    counted = _pass(series, rule, series.start, HORIZON, (), spend)
    current = next(counted, None)  # DTSTART: always the first
    plain = sorted({series.start, *rdates})
    for lo, hi in _spans(los, his):
        found = set(plain[bisect_left(plain, lo) : bisect_right(plain, hi)])
        if current is not None:
            for wall in _pass(pattern, uncounted, lo, hi, (), spend):
                while current is not None and current < wall:
                    current = next(counted, None)
                if current is None:
                    break
                if current == wall:
                    found.add(wall)
        yield from sorted(found)


def _passes(
    series: Series,
    rule: ParsedRule | None,
    los: list[datetime],
    his: list[datetime],
    rdates: list[datetime],
    spend: Spend,
) -> Iterator[datetime]:
    for lo, hi in _spans(los, his):
        own = rdates[bisect_left(rdates, lo) : bisect_right(rdates, hi)]
        yield from _pass(series, rule, lo, hi, own, spend)


def _pass(
    series: Series,
    rule: ParsedRule | None,
    lo: datetime,
    hi: datetime,
    rdates: Sequence[datetime],
    spend: Spend,
) -> Iterator[datetime]:
    """The series' wall times from `lo` to `hi` (its RDATEs among them: `rdates`),
    charged as the scan goes."""
    counter = Counter()
    spend((recurrence_cost.period(rule) if rule else 0) + len(rdates))
    last = lo
    for wall in walls(series, lo, hi, counter, keep_exdates=True, rdates=rdates):
        spend(recurrence_cost.WALL + (recurrence_cost.periods(rule, last, wall) if rule else 0))
        last = wall
        yield wall
    if rule is not None and counter.reached is not None:
        spend(recurrence_cost.periods(rule, last, counter.reached))


def _spans(los: list[datetime], his: list[datetime]) -> Iterator[tuple[datetime, datetime]]:
    lo, hi = los[0], his[0]
    for next_lo, next_hi in zip(los[1:], his[1:], strict=True):
        if next_lo - hi > CLUSTER:
            yield lo, hi
            lo = next_lo
        hi = max(hi, next_hi)
    yield lo, hi
