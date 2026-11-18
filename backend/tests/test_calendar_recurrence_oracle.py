"""Recurrence against an oracle that does not use `dateutil` (review of M10 Task 2,
M-9): a brute-force expander written from RFC 5545 3.3.10. Each period's whole set is
built (a week from WKST, a month, a year), BYSETPOS picks from it, then what lies before
DTSTART goes, DTSTART comes first and COUNT counts it, UNTIL is inclusive.

Seeded, a few seconds: 1,200 accepted random rules of every part the calendar takes,
started on any day (the 29th to 31st too) in UTC at 09:00, so a day stands for an
occurrence. The same rules check that the canonical text reads back as itself.
"""

import calendar
import random
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta

from app.modules.calendars import recurrence
from app.modules.calendars.recurrence import Series
from app.modules.calendars.recurrence_rule import WEEKDAYS, Freq, ParsedRule, parse_rule

SEED = 20261119
RULES = 1200
HOUR = timedelta(hours=1)
THIRTY_YEARS = timedelta(days=30 * 366)


def _month(year: int, month: int) -> list[date]:
    return [date(year, month, day) for day in range(1, calendar.monthrange(year, month)[1] + 1)]


def _nth(days: list[date], weekday: int, n: int) -> list[date]:
    """The `n`th `weekday` among `days` (all of them for 0; from the end when < 0)."""
    found = [day for day in days if day.weekday() == weekday]
    if n == 0:
        return found
    index = n - 1 if n > 0 else len(found) + n
    return [found[index]] if 0 <= index < len(found) else []


def _monthdays(rule: ParsedRule, days: list[date]) -> set[date]:
    """BYMONTHDAY within one month's `days` (negative from its end)."""
    picked = {k - 1 if k > 0 else len(days) + k for k in rule.bymonthday}
    return {days[i] for i in picked if 0 <= i < len(days)}


def _in_month_or_year(rule: ParsedRule, start: date, months: list[list[date]]) -> list[date]:
    """The set of a month (`months` holds one) or a year (each of its months)."""
    sets: list[set[date]] = []
    if rule.bymonthday:
        sets.append(set().union(*(_monthdays(rule, days) for days in months)))
    if rule.byday:
        # BYDAY is one list: a plain day is all such days, a numbered one the nth; the
        # nth counts within the month, or within the year of a YEARLY rule without BYMONTH.
        ranges = (
            [[d for days in months for d in days]]
            if rule.freq is Freq.YEARLY and not rule.bymonth
            else months
        )
        sets.append({d for days in ranges for wd, n in rule.byday for d in _nth(days, wd, n)})
    if not sets:  # the day of the month (and the month, for a yearly rule) of DTSTART
        same_month = rule.freq is Freq.MONTHLY or rule.bymonth
        sets.append(
            {
                d
                for days in months
                for d in days
                if d.day == start.day and (same_month or d.month == start.month)
            }
        )
    return sorted(set.intersection(*sets))


def _periods(rule: ParsedRule, start: date, last: date) -> Iterator[list[date]]:
    """Each period's whole set, from the one DTSTART lies in, until `last`."""
    if rule.freq is Freq.DAILY:
        day = start
        while day <= last:
            keep = (not rule.bymonth or day.month in rule.bymonth) and (
                not rule.byday or any(wd == day.weekday() for wd, _ in rule.byday)
            )
            if rule.bymonthday:
                keep = keep and day in _monthdays(rule, _month(day.year, day.month))
            yield [day] if keep else []
            day += timedelta(days=rule.interval)
    elif rule.freq is Freq.WEEKLY:
        week = start - timedelta(days=(start.weekday() - rule.wkst) % 7)
        weekdays = {wd for wd, _ in rule.byday} or {start.weekday()}
        while week <= last:
            days = [week + timedelta(days=i) for i in range(7)]
            yield [
                d
                for d in days
                if d.weekday() in weekdays and (not rule.bymonth or d.month in rule.bymonth)
            ]
            week += timedelta(weeks=rule.interval)
    elif rule.freq is Freq.MONTHLY:
        index = start.year * 12 + start.month - 1
        while date(index // 12, index % 12 + 1, 1) <= last:
            year, month = index // 12, index % 12 + 1
            in_month = not rule.bymonth or month in rule.bymonth
            yield _in_month_or_year(rule, start, [_month(year, month)]) if in_month else []
            index += rule.interval
    else:
        for year in range(start.year, last.year + 1, rule.interval):
            months = rule.bymonth or tuple(range(1, 13))
            yield _in_month_or_year(rule, start, [_month(year, m) for m in months])


def expected(rule: ParsedRule, start: date, last: date) -> list[date]:
    found = [start]
    for period in _periods(rule, start, last):
        if rule.bysetpos:
            picked = {p - 1 if p > 0 else len(period) + p for p in rule.bysetpos}
            period = sorted(period[i] for i in picked if 0 <= i < len(period))
        found += [day for day in period if start < day <= last]
        if rule.count is not None and len(found) >= rule.count:
            return found[: rule.count]
    return found


def _rule_text(rng: random.Random) -> str:
    freq = rng.choice(list(Freq))
    parts = [f"FREQ={freq}"]
    if rng.random() < 0.4:
        parts.append(f"INTERVAL={rng.randint(2, 5)}")
    by_month = rng.random() < 0.35
    if by_month:
        parts.append("BYMONTH=" + ",".join(map(str, rng.sample(range(1, 13), rng.randint(1, 4)))))
    if freq is not Freq.WEEKLY and rng.random() < 0.35:
        days = rng.sample([1, 2, 13, 15, 28, 29, 30, 31, -1, -2, -30, -31], rng.randint(1, 3))
        parts.append("BYMONTHDAY=" + ",".join(map(str, days)))
    if rng.random() < 0.55:
        numbered = freq in (Freq.MONTHLY, Freq.YEARLY)
        top = 5 if freq is Freq.MONTHLY or by_month else 53
        share = rng.choice([0.0, 0.5, 1.0])  # plain, mixed (R2-1) or all numbered
        days = [
            (
                str(rng.choice([1, 2, 3, -1, -2, top, -top]))
                if numbered and rng.random() < share
                else ""
            )
            + wd
            for wd in rng.sample(WEEKDAYS, rng.randint(1, 4))
        ]
        parts.append("BYDAY=" + ",".join(days))
    if rng.random() < 0.4:  # without another BYxxx part refused, and skipped
        # A daily period holds one day: other positions never match (and are refused).
        positions = [1, -1] if freq is Freq.DAILY else [1, 2, 3, -1, -2, 5]
        parts.append("BYSETPOS=" + ",".join(map(str, rng.sample(positions, rng.randint(1, 2)))))
    if rng.random() < 0.4:
        parts.append("WKST=" + rng.choice(WEEKDAYS))
    end = rng.random()
    if end < 0.3:
        parts.append(f"COUNT={rng.randint(1, 40)}")
    elif end < 0.5:
        until = date(2026, 1, 1) + timedelta(days=rng.randint(-2000, 3000))
        parts.append(f"UNTIL={until:%Y%m%d}T{rng.choice(['085959', '090000', '235959'])}Z")
    rng.shuffle(parts)
    return ";".join(parts).lower() if rng.random() < 0.1 else ";".join(parts)


def _start(rng: random.Random) -> datetime:
    start = datetime(rng.randint(2019, 2026), rng.randint(1, 12), rng.randint(1, 28), 9)
    if rng.random() < 0.2:
        return start.replace(
            month=rng.choice([1, 3, 5, 7, 8, 10, 12]), day=rng.choice([29, 30, 31])
        )
    return start


def test_occurrences_agree_with_an_rfc_oracle() -> None:
    rng = random.Random(SEED)
    checked, divergent = 0, []
    while checked < RULES:
        text = _rule_text(rng)
        try:
            canonical = recurrence.check_rule(text)
        except recurrence.RuleInvalid:
            continue
        assert recurrence.check_rule(canonical) == canonical, text
        rule = parse_rule(canonical)
        start = _start(rng)
        series = Series(start, HOUR, "UTC", False, canonical)
        try:
            recurrence.check_series(series)
        except recurrence.RuleInvalid:  # refused as never matching: it must not match
            if expected(rule, start.date(), start.date() + THIRTY_YEARS) != [start.date()]:
                divergent.append(f"{canonical} from {start:%a %Y-%m-%d} refused")
            continue
        last = (start + timedelta(days=rng.choice([60, 400, 1500, 3700]))).date()
        if isinstance(rule.until, datetime):
            last = min(last, (rule.until - timedelta(hours=9)).date())
        last = max(last, start.date())
        window = (
            start.replace(tzinfo=UTC),
            datetime.combine(last + timedelta(days=1), time(), UTC),
        )
        found = [
            o.recurrence_id.date() for o in recurrence.occurrences(series, *window, limit=10**6)
        ]
        if found != expected(rule, start.date(), last):
            divergent.append(f"{canonical} from {start:%a %Y-%m-%d}")
        checked += 1
    assert divergent == []
