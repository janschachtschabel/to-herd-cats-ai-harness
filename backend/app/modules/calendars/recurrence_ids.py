"""Many recurrence ids of one series at once (review M10 Task 7a, R7a-4 and R7a-6): what
`recurrence.is_occurrence` and `recurrence.recurrence_id_at` answer for each of many
values, at the cost of one expansion per stretch of them instead of one per value.

A counted rule counts from its start, so each call of the single-value functions
expands it from there; here it is expanded once, up to the latest value. Any other
series is expanded over each cluster of values (values closer than `CLUSTER` share a
pass), each pass jumping to its cluster. `spend` is told of the work as it goes (one
unit per wall time looked at) and may stop it by raising.
"""

from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, timedelta

from app.modules.calendars.recurrence import SLACK, walls
from app.modules.calendars.recurrence_jump import Counter
from app.modules.calendars.recurrence_series import Series, bounded, instant, wall_of

CLUSTER = timedelta(days=31)
_STEP = 256  # wall times between two calls of `spend`


def named(
    series: Series, values: Iterable[datetime], spend: Callable[[int], None]
) -> frozenset[datetime]:
    """Which of the wall times `values` the series names as occurrences, deleted ones
    too (`is_occurrence` for each)."""
    wanted = frozenset(values)
    ordered = sorted(wanted)
    return frozenset(wall for wall in _passes(series, ordered, ordered, spend) if wall in wanted)


def ids_at(
    series: Series, moments: Iterable[datetime], spend: Callable[[int], None]
) -> dict[datetime, datetime]:
    """The recurrence id of the occurrence (deleted ones too) that starts at each
    instant of `moments` that has one; of two at one instant the earlier
    (`recurrence_id_at` for each)."""
    wanted = frozenset(m for m in moments if bounded(m) == m)
    centres = sorted(wall_of(series, m) for m in wanted)
    found: dict[datetime, datetime] = {}
    for wall in _passes(series, [c - SLACK for c in centres], [c + SLACK for c in centres], spend):
        moment = instant(series, wall)
        if moment in wanted and moment not in found:
            found[moment] = wall
    return found


def _passes(
    series: Series, los: list[datetime], his: list[datetime], spend: Callable[[int], None]
) -> Iterator[datetime]:
    """The series' wall times (deleted ones too) over the spans `[los[i], his[i]]`
    (both sorted), in order and once."""
    looked = 0
    for lo, hi in _spans(series, los, his):
        for wall in walls(series, lo, hi, Counter(), keep_exdates=True):
            looked += 1
            if looked % _STEP == 0:
                spend(_STEP)
            yield wall
    spend(looked % _STEP + 1)


def _spans(
    series: Series, los: list[datetime], his: list[datetime]
) -> Iterator[tuple[datetime, datetime]]:
    if not los:
        return
    rule = series.rule
    if rule is None or rule.count is not None:
        yield los[0], max(his)  # counted from the start anyway: one pass
        return
    lo, hi = los[0], his[0]
    for next_lo, next_hi in zip(los[1:], his[1:], strict=True):
        if next_lo - hi > CLUSTER:
            yield lo, hi
            lo = next_lo
        hi = max(hi, next_hi)
    yield lo, hi
