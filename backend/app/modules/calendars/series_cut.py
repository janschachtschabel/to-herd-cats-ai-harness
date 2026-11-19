"""Where a series splits (plan M10 decision 6, I5; review M10 task 3b, R3b-3, R3b-4,
R3b-7): pure, no database.

A part split off keeps the series' pattern only if it starts at an occurrence that can
be a series start: one the rule names (DTSTART or a match, not an RDATE alone; else
the rule's weekday, day, phase of `INTERVAL` and time of day would come from the RDATE)
whose wall time is its start's (not in a clock-change gap; a start is stored as an
instant, and 02:30 on the day the clocks jump from 02:00 to 03:00 is no instant). That
occurrence is the **anchor**. When the series has no rule occurrence left from the
split on, any RDATE that is no gap time anchors (a part without a rule has no pattern
to keep).

`cut(series, wall)` splits at the occurrence `wall`: the old part ends just before the
anchor (its rule gets an `UNTIL`, replacing a `COUNT`; a rule that has nothing left is
kept as it is), the new part starts at the anchor with the rest of the rule written
out (`rule_after`: the weekday, day and month an implicit rule takes from DTSTART,
`explicit_rule`; a counted rule keeps the rest of its count) and the RDATEs and
EXDATEs from the anchor on. The live occurrences from `wall` up to the anchor (RDATEs
and gap occurrences: the **strays**) stay with the old part; the caller gives them the
change as overrides. Without a change the occurrences of both parts are exactly the
series' own (`tests/test_series_cut_property.py`).
"""

import dataclasses
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import islice

from app.modules.calendars import recurrence
from app.modules.calendars.event_models import DATES_MAX
from app.modules.calendars.recurrence import HORIZON, Series, SeriesInvalid
from app.modules.calendars.recurrence_jump import Counter
from app.modules.calendars.recurrence_rule import Freq, ParsedRule
from app.modules.calendars.recurrence_series import instant, wall_of

# How many rule occurrences in a row may lie in gaps before no anchor is looked for.
ANCHOR_SEARCH = 1000


@dataclass(frozen=True, slots=True)
class Cut:
    old: Series  # the part before the anchor, strays included
    new: Series | None  # from the anchor on; None: no live occurrence to start a part
    anchor: datetime | None
    strays: tuple[datetime, ...]  # live occurrences from the split up to the anchor


def explicit_rule(rule: ParsedRule, start: datetime) -> ParsedRule:
    """The rule with what it takes from DTSTART written out (RFC 5545 3.3.10, as
    `recurrence` expands it): a weekly rule's weekday, a monthly rule's day, a yearly
    rule's month and day, each only where the rule names neither BYDAY nor
    BYMONTHDAY."""
    if rule.bymonthday or rule.byday:
        return rule
    if rule.freq is Freq.YEARLY:
        return dataclasses.replace(
            rule, bymonth=rule.bymonth or (start.month,), bymonthday=(start.day,)
        )
    if rule.freq is Freq.MONTHLY:
        return dataclasses.replace(rule, bymonthday=(start.day,))
    if rule.freq is Freq.WEEKLY:
        return dataclasses.replace(rule, byday=((start.weekday(), 0),))
    return rule


def round_trips(series: Series, wall: datetime) -> bool:
    """Whether `wall` is the wall time of its own start (not in a gap)."""
    return series.tzid is None or wall_of(series, instant(series, wall)) == wall


def _rule_from(series: Series, wall: datetime) -> list[datetime] | None:
    """The rule's occurrences from `wall` on, up to its first that round-trips (deleted
    ones too); None when it has none from there."""
    found: list[datetime] = []
    for match in recurrence.rule_walls(series, wall, HORIZON, Counter()):
        if match < wall:
            continue
        found.append(match)
        if round_trips(series, match) or len(found) > ANCHOR_SEARCH:
            return found
    return found or None


def anchor_at(series: Series, wall: datetime) -> datetime | None:
    """The first occurrence from `wall` on that can start a part keeping the pattern."""
    if series.rule is not None:
        matches = _rule_from(series, wall)
        if matches is not None:
            last = matches[-1]
            return last if round_trips(series, last) else None
    rdates = sorted(d for d in set(series.rdates) if d >= wall)
    return next((d for d in rdates if round_trips(series, d)), None)


def first_live(series: Series) -> datetime | None:
    """The series' first occurrence that is not deleted (what "the first" means for
    splitting and deleting: review M10 task 3b, R3b-7); None when none is left."""
    return next(recurrence.walls(series, series.start, HORIZON, Counter()), None)


def until_before(series: Series, wall: datetime) -> str | None:
    """The series' rule ending just before its occurrence `wall`: `UNTIL` one second
    before it starts (all-day: the day before), in place of a `COUNT`."""
    rule = series.rule
    if rule is None:
        return None
    until: date | datetime
    if series.all_day:
        until = wall.date() - timedelta(days=1)
    else:
        until = instant(series, wall) - timedelta(seconds=1)
    if rule.until is not None and type(rule.until) is type(until) and rule.until < until:
        until = rule.until
    return dataclasses.replace(rule, count=None, until=until).text


def rule_after(series: Series, wall: datetime) -> str | None:
    """The rule of the part from its rule occurrence `wall` on, written out
    (`explicit_rule`): a counted one keeps the rest (deleted occurrences count)."""
    rule = series.rule
    if rule is None:
        return None
    rule = explicit_rule(rule, series.start)
    if rule.count is not None:
        rest = rule.count - recurrence.count_before(series, wall)
        rule = dataclasses.replace(rule, count=rest)
    return rule.text


def _strays(series: Series, wall: datetime, anchor: datetime | None) -> tuple[datetime, ...]:
    found = recurrence.walls(series, wall, anchor or HORIZON, Counter())
    strays = tuple(w for w in islice(found, DATES_MAX + 2) if anchor is None or w < anchor)
    if len(strays) > DATES_MAX:
        raise SeriesInvalid("event.too_many_dates")
    return strays


def cut(series: Series, wall: datetime, *, keep_pattern: bool = True) -> Cut:
    """Splits `series` at its occurrence `wall`. `keep_pattern=False` (a change that
    names a rule or dates of its own, or deleting this and the following) anchors at
    `wall` itself."""
    anchor = anchor_at(series, wall) if keep_pattern else wall
    strays = _strays(series, wall, anchor)
    if anchor is None:
        return Cut(series, None, None, strays)
    later = recurrence.rule_walls(series, anchor, HORIZON, Counter())
    next_by_rule = next((w for w in later if w >= anchor), None)
    ruled = next_by_rule == anchor  # the anchor is the rule's: the new part keeps it
    old = dataclasses.replace(
        series,
        # a rule with nothing left from the anchor on stays as it is (its COUNT holds)
        rrule=series.rrule if next_by_rule is None else until_before(series, anchor),
        rdates=tuple(d for d in series.rdates if d < anchor),
        exdates=tuple(d for d in series.exdates if d < anchor),
    )
    new = Series(
        start=anchor,
        duration=series.duration,
        tzid=series.tzid,
        all_day=series.all_day,
        rrule=rule_after(series, anchor) if ruled else None,
        rdates=tuple(d for d in series.rdates if d > anchor or (ruled and d == anchor)),
        exdates=tuple(d for d in series.exdates if d >= anchor),
    )
    return Cut(old, new if first_live(new) is not None else None, anchor, strays)
