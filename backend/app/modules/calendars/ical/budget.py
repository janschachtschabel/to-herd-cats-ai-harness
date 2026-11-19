"""One bound on the work of one `reading.parse` (review M10 Task 7a, R7a-1, R7a-2,
R7a-4): operations are counted, never the clock, so the same file always gets as far.

What costs more than reading its own bytes is charged, in units of about a microsecond
of work (two Python calls): comparing a file's VTIMEZONE with `tzdata` (a definition's
offset at one wall time: `offset_cost`; four `tzdata` look-ups: one), checking a rule
(`check_cost`: the periods `dateutil` scanned to its first match, or to the horizon), and
expanding a series to match recurrence ids (one per wall time).
Once `WORK_LIMIT` is spent, the event being read and every later one are skipped and
counted as `ical.over_budget`; `parse` never raises for it.
"""

from datetime import datetime

from app.modules.calendars.ical import problems
from app.modules.calendars.ical.problems import Skip
from app.modules.calendars.recurrence_rule import LAST_YEAR, Freq, ParsedRule

WORK_LIMIT = 2_000_000
# What one period of `dateutil`'s scan costs, by FREQ (measured: a yearly period builds
# a year's masks, a daily one tests a day).
_PERIOD = {Freq.DAILY: 1, Freq.WEEKLY: 3, Freq.MONTHLY: 4, Freq.YEARLY: 25}
_PERIOD_DAYS = {Freq.DAILY: 1, Freq.WEEKLY: 7, Freq.MONTHLY: 28, Freq.YEARLY: 365}
_RULED = 12  # one observance's rule, asked for its onsets near one year


def check_cost(rule: ParsedRule, start: datetime, first: datetime | None) -> int:
    """What checking `rule` from `start` cost: the periods to its first match (None:
    it never matched, so to the horizon)."""
    end = first if first is not None else datetime(LAST_YEAR, 12, 31)
    periods = max((end - start).days, 0) // (_PERIOD_DAYS[rule.freq] * rule.interval) + 1
    return 10 + periods * _PERIOD[rule.freq]


def offset_cost(ruled: int) -> int:
    """What one `vtimezone.Definition.offset_at` costs for a definition with `ruled`
    observances that follow a rule."""
    return 1 + ruled * _RULED


class OverBudget(Skip):
    def __init__(self) -> None:
        super().__init__(problems.OVER_BUDGET)


class Budget:
    __slots__ = ("left",)

    def __init__(self, limit: int | None = None) -> None:
        self.left = WORK_LIMIT if limit is None else limit

    def spend(self, units: int) -> None:
        self.left -= units
        if self.left < 0:
            raise OverBudget()

    @property
    def exhausted(self) -> bool:
        return self.left < 0
