"""The rule's matches, from `dateutil` (plan M10 decision 6): the one module of the
calendar that talks to it (`tests/test_calendar_imports.py`), pure.

- A rule runs in wall time (naive `datetime`s), with the defaults `dateutil` would take
  from DTSTART taken from the series' original start (`_kwargs`), so it can run from a
  start moved on by a jump. BYDAY is read as RFC 5545's one list (`_byweekday`), a
  weekly BYSETPOS over the whole first week.
- `dateutil` scans periods without a candidate until its `MAXYEAR`, so it runs 7,600
  years (19 Gregorian cycles: the same weekdays and leap years) ahead of us, where its
  `MAXYEAR` 9999 is our 2399 (`HORIZON`): the scan of a sparse rule is bounded there.
"""

from collections.abc import Iterator
from datetime import datetime
from typing import Any

from dateutil.rrule import DAILY, MONTHLY, WEEKLY, YEARLY, rrule, weekday

from app.modules.calendars.recurrence_jump import Counter, week_start
from app.modules.calendars.recurrence_rule import LAST_YEAR, Freq, ParsedRule

HORIZON = datetime(LAST_YEAR, 12, 31, 23, 59, 59)
_AHEAD_YEARS = 7600
_FREQS = {Freq.DAILY: DAILY, Freq.WEEKLY: WEEKLY, Freq.MONTHLY: MONTHLY, Freq.YEARLY: YEARLY}


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


def matches(
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
    # `dateutil` checks an UNTIL at candidates only: it scans to the first one past it
    # either way; stopping there here lets the counter see how far the scan reached.
    until = min(stop, HORIZON)
    for found in rrule(dtstart=_ahead(first), cache=False, **_kwargs(rule, start)):
        counter.candidates += 1
        wall = found.replace(year=found.year - _AHEAD_YEARS)
        counter.reached = wall
        if wall > until:
            return
        if wall >= begin:
            yield wall
    counter.reached = HORIZON  # scanned to `dateutil`'s last year
