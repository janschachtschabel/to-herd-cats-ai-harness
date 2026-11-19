"""What expanding a rule costs (re-check M10 Task 7a, RC7a-2): `dateutil` scans a rule
period by period, whether a period holds a match or not, so the work of a pass is the
periods it scans, not the matches it finds. Units are about a microsecond of work (two
Python calls), as `ical.budget` counts them.

Measured (Python 3.13, `dateutil` 4.0): a period costs about 1.8 calls (DAILY),
4 (WEEKLY), 2 to 4 (MONTHLY) and 4 to 9 calls but 19 to 27 µs (YEARLY, which builds
the year's masks); DAILY and WEEKLY periods spanning many days cost about six calls
more per month crossed. A wall time passing through the expansion's generators costs
about six calls.
"""

from datetime import datetime

from app.modules.calendars.recurrence_rule import Freq, ParsedRule

_BASE = {Freq.DAILY: 1, Freq.WEEKLY: 2, Freq.MONTHLY: 4, Freq.YEARLY: 25}
_DAYS = {Freq.DAILY: 1, Freq.WEEKLY: 7, Freq.MONTHLY: 28, Freq.YEARLY: 365}
WALL = 3  # one wall time through the generators of `recurrence.walls`


def period(rule: ParsedRule) -> int:
    """What one period of `rule` costs to scan."""
    span = _DAYS[rule.freq] * rule.interval
    return _BASE[rule.freq] + (span // 5 if rule.freq in (Freq.DAILY, Freq.WEEKLY) else 0)


def periods(rule: ParsedRule, begin: datetime, end: datetime) -> int:
    """What scanning `rule` from `begin` to `end` costs (whole periods in between)."""
    days = max((end - begin).days, 0)
    return days // (_DAYS[rule.freq] * rule.interval) * period(rule)
