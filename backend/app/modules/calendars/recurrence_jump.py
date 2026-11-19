"""The fast-forward of a rule (plan M10 decision 6, I7): pure calendar arithmetic.

`dateutil.rrule` counts from DTSTART, so a window decades after it would walk through
every period in between. `jump` moves the start on by k·`INTERVAL` whole periods of
`FREQ` (days; weeks aligned to `WKST`; calendar months; calendar years), to the
beginning of the last such period that begins no later than the window. The phase of
`INTERVAL` stays, and so does every period's set for `BYSETPOS` (the new start is the
first moment of its period at the series' time of day, so no candidate of the period
lies before it). A counted rule does not jump here: `COUNT` counts from DTSTART.
`counted_jump` moves one on only when every active period holds the same number of
matches (`recurrence_count.per_block`), and says how many occurrences it skipped.

The caller resolves the rule's defaults (`BYDAY` of a weekly rule, the day of a
monthly one) from the original start before it runs the rule from the jumped one.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.modules.calendars.recurrence_count import Unit, per_block
from app.modules.calendars.recurrence_rule import Freq, ParsedRule


@dataclass(slots=True)
class Counter:
    """What an expansion cost: candidates the rule generated, whether it jumped, and
    the wall time its scan reached (the last candidate, or the horizon where the rule
    ran out: `recurrence_ids` charges the periods scanned past what it asked for)."""

    candidates: int = 0
    jumps: int = 0
    reached: datetime | None = None


def week_start(day: date, wkst: int) -> date:
    return day - timedelta(days=(day.weekday() - wkst) % 7)


def _first_of_month(start: datetime, months: int) -> date:
    index = start.year * 12 + start.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def jump(rule: ParsedRule, start: datetime, window_from: datetime) -> datetime:
    """The start to run `rule` from for wall times from `window_from` on (`start` itself
    when the rule is counted or the window does not lie after the start)."""
    if rule.count is not None or window_from <= start:
        return start
    step = rule.interval
    if rule.freq is Freq.DAILY:
        periods = (window_from.date() - start.date()).days // step
        begin = start.date() + timedelta(days=periods * step)
    elif rule.freq is Freq.WEEKLY:
        first = week_start(start.date(), rule.wkst)
        weeks = (week_start(window_from.date(), rule.wkst) - first).days // 7
        begin = first + timedelta(weeks=weeks // step * step)
    elif rule.freq is Freq.MONTHLY:
        months = (window_from.year - start.year) * 12 + window_from.month - start.month
        begin = _first_of_month(start, months // step * step)
    else:
        years = (window_from.year - start.year) // step * step
        begin = date(start.year + years, 1, 1)
    jumped = datetime.combine(begin, start.time())
    return jumped if jumped > start else start


def _origin(rule: ParsedRule, start: datetime) -> date:
    """Where the first block begins: DTSTART's day, week (from WKST), month or year."""
    if rule.freq is Freq.DAILY:
        return start.date()
    if rule.freq is Freq.WEEKLY:
        return week_start(start.date(), rule.wkst)
    if rule.freq is Freq.MONTHLY:
        return date(start.year, start.month, 1)
    return date(start.year, 1, 1)


def _units_between(origin: date, day: date, unit: Unit) -> int:
    if unit is Unit.DAY:
        return (day - origin).days
    if unit is Unit.MONTH:
        return (day.year - origin.year) * 12 + day.month - origin.month
    return day.year - origin.year


def _advance(origin: date, units: int, unit: Unit) -> date:
    if unit is Unit.DAY:
        return origin + timedelta(days=units)
    if unit is Unit.MONTH:
        return _first_of_month(datetime.combine(origin, datetime.min.time()), units)
    return date(origin.year + units, 1, 1)


def counted_jump(
    rule: ParsedRule, start: datetime, window_from: datetime, count_first: Callable[[datetime], int]
) -> tuple[datetime, int] | None:
    """For a counted rule whose every active period holds the same number of matches:
    the start of the block that holds `window_from` (at the series' time of day) and
    how many of its occurrences lie before it (DTSTART, the matches of the first block
    after it, then n per whole block). `count_first(stop)` gives the rule's matches
    after DTSTART and before `stop`, the end of the first block. None when the rule is
    not counted, its count per period may vary, or the window lies in the first block:
    then it walks from DTSTART."""
    if rule.count is None or window_from <= start:
        return None
    shape = per_block(rule, start)
    if shape is None:
        return None
    unit, length, per = shape
    origin = _origin(rule, start)
    blocks = _units_between(origin, window_from.date(), unit) // length
    if blocks < 1:
        return None
    first_end = datetime.combine(_advance(origin, length, unit), start.time())
    begin = datetime.combine(_advance(origin, blocks * length, unit), start.time())
    return begin, 1 + count_first(first_end) + (blocks - 1) * per
