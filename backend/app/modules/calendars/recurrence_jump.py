"""The fast-forward of a rule (plan M10 decision 6, I7): pure calendar arithmetic.

`dateutil.rrule` counts from DTSTART, so a window decades after it would walk through
every period in between. `jump` moves the start on by k·`INTERVAL` whole periods of
`FREQ` (days; weeks aligned to `WKST`; calendar months; calendar years), to the
beginning of the last such period that begins no later than the window. The phase of
`INTERVAL` stays, and so does every period's set for `BYSETPOS` (the new start is the
first moment of its period at the series' time of day, so no candidate of the period
lies before it). A counted rule never jumps: `COUNT` counts from DTSTART.

The caller resolves the rule's defaults (`BYDAY` of a weekly rule, the day of a
monthly one) from the original start before it runs the rule from the jumped one.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

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
