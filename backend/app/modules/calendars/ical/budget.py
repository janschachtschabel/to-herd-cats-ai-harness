"""One bound on the work of one `reading.parse` (review M10 Task 7a, R7a-1, R7a-2,
R7a-4): operations are counted, never the clock, so the same file always gets as far.

What costs more than reading its own bytes is charged, in units of about a microsecond
of work (two Python calls), where the work is done and before it (re-check RC7a-1 to
RC7a-5: cost is work): comparing a file's VTIMEZONE with `tzdata` (building a
definition: its size; a definition's offset at one wall time:
`vtimezone.Definition.offset_at` tells its own work; four `tzdata` look-ups: one; a
name looked up: one), checking a rule
(`check_cost`: the periods `dateutil` scanned to its first match, or to the horizon), and
expanding a series to match recurrence ids (`recurrence_ids`: the periods scanned and
the wall times found, priced by `recurrence_cost`).
Once `WORK_LIMIT` is spent, the event being read and every later one are skipped and
counted as `ical.over_budget`; `parse` never raises for it.
"""

from datetime import datetime

from app.modules.calendars import recurrence_cost
from app.modules.calendars.ical import problems
from app.modules.calendars.ical.problems import Skip
from app.modules.calendars.recurrence_rule import LAST_YEAR, ParsedRule

WORK_LIMIT = 2_000_000


def check_cost(rule: ParsedRule, start: datetime, first: datetime | None) -> int:
    """What checking `rule` from `start` cost: the periods to its first match (None:
    it never matched, so to the horizon)."""
    end = first if first is not None else datetime(LAST_YEAR, 12, 31)
    return 10 + recurrence_cost.period(rule) + recurrence_cost.periods(rule, start, end)


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
