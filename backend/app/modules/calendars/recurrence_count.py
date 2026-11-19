"""Whether a rule holds the same number of matches in every active period (plan M10
Task 3c, remedy b): pure calendar arithmetic, no library. A counted rule (`COUNT`) may
jump ahead only then (`recurrence_jump.counted_jump`): it skips whole blocks and adds
their matches, n per block, to what it counted. Anything not shown fixed here walks.

A block is `INTERVAL` periods of `FREQ` from the period of DTSTART (days; weeks from
WKST; months; years); only its first period is active. Fixed, and how many per block:

- `DAILY` without BY parts: 1. With plain `BYDAY` only: blocks of lcm(`INTERVAL`, 7)
  days, the matching days of one such block (the weekdays repeat).
- `WEEKLY` with plain `BYDAY` (or DTSTART's day), no `BYMONTH`, `BYMONTHDAY` or
  `BYSETPOS`: the number of days.
- `MONTHLY` without `BYMONTH`: `BYMONTHDAY` (or DTSTART's day) that every month has and
  where no day from the start ever meets one from the end; or numbered `BYDAY` within
  ±4 where no nth meets an nth from the end of the same weekday; or plain `BYDAY` with
  `BYSETPOS` whose positions every month's set holds and never meet.
- `YEARLY` without `BYSETPOS`: the same per month of `BYMONTH` (or DTSTART's month;
  with `BYMONTHDAY` and no `BYMONTH`, every month), numbered `BYDAY` only with
  `BYMONTH`.
"""

import math
from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import StrEnum

from app.modules.calendars.recurrence_rule import Freq, ParsedRule

# The fewest and the most days each month has (February: 28 or 29).
_MIN_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_MAX_DAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_ALL_MONTHS = range(1, 13)


class Unit(StrEnum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"


def _meet(firsts: Iterable[int], lasts: Iterable[int], low: int, high: int) -> bool:
    """Whether a position from the start (p > 0) and one from the end (q < 0) of a set
    of `low` to `high` elements ever name the same element (p + |q| − 1 = size)."""
    return any(low <= p - q - 1 <= high for p in firsts if p > 0 for q in lasts if q < 0)


def _monthdays(days: tuple[int, ...], months: Iterable[int]) -> int | None:
    """Matches per month of `months` holding every day of `days` (none meeting another
    from the other end), times the number of those months; None if one may lack one."""
    picked = set(months)
    for month in picked:
        low, high = _MIN_DAYS[month - 1], _MAX_DAYS[month - 1]
        if any(abs(day) > low for day in days) or _meet(days, days, low, high):
            return None
    return len(set(days)) * len(picked)


def _ordinals(byday: tuple[tuple[int, int], ...], months: int) -> int | None:
    """Numbered weekdays per month: each weekday occurs 4 or 5 times in a month."""
    if any(n == 0 or abs(n) > 4 for _, n in byday):
        return None
    for weekday in {day for day, _ in byday}:
        numbers = [n for day, n in byday if day == weekday]
        if _meet(numbers, numbers, 4, 5):
            return None
    return len(set(byday)) * months


def _setpos(rule: ParsedRule) -> int | None:
    """Plain weekdays of a month picked by BYSETPOS: the set holds 4 to 5 of each."""
    if rule.bymonthday or not rule.byday or any(n for _, n in rule.byday):
        return None
    low = 4 * len({day for day, _ in rule.byday})
    high = 5 * len({day for day, _ in rule.byday})
    positions = rule.bysetpos
    if any(abs(p) > low for p in positions) or _meet(positions, positions, low, high):
        return None
    return len(set(positions))


def _monthly(rule: ParsedRule, start: datetime) -> int | None:
    if rule.bymonth:
        return None
    if rule.bysetpos:
        return _setpos(rule)
    if rule.byday:
        return None if rule.bymonthday else _ordinals(rule.byday, 1)
    per_year = _monthdays(rule.bymonthday or (start.day,), _ALL_MONTHS)
    return None if per_year is None else per_year // len(_ALL_MONTHS)


def _yearly(rule: ParsedRule, start: datetime) -> int | None:
    if rule.bysetpos:
        return None
    if rule.byday:
        if not rule.bymonth or rule.bymonthday:
            return None
        return _ordinals(rule.byday, len(set(rule.bymonth)))
    if rule.bymonthday:
        return _monthdays(rule.bymonthday, rule.bymonth or _ALL_MONTHS)
    return _monthdays((start.day,), rule.bymonth or (start.month,))


def per_block(rule: ParsedRule, start: datetime) -> tuple[Unit, int, int] | None:
    """(unit, block length in units, matches per block) of a rule whose every active
    period holds the same number of matches; None when it may vary."""
    plain = all(n == 0 for _, n in rule.byday)
    days = {day for day, _ in rule.byday}
    step = rule.interval
    if rule.freq is Freq.DAILY:
        if rule.bymonth or rule.bymonthday or rule.bysetpos or not plain:
            return None
        if not days:
            return Unit.DAY, step, 1
        length = math.lcm(step, 7)
        first = start.date()
        hits = sum((first + timedelta(days=t)).weekday() in days for t in range(0, length, step))
        return (Unit.DAY, length, hits) if hits else None
    if rule.freq is Freq.WEEKLY:
        if rule.bymonth or rule.bymonthday or rule.bysetpos or not plain:
            return None
        return Unit.DAY, 7 * step, len(days) or 1
    found = _monthly(rule, start) if rule.freq is Freq.MONTHLY else _yearly(rule, start)
    unit = Unit.MONTH if rule.freq is Freq.MONTHLY else Unit.YEAR
    return None if not found else (unit, step, found)
