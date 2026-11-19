"""The offsets a file's VTIMEZONE gives (RFC 5545 3.6.5), to compare with `tzdata`
(`zones`); never used to place an event itself.

Observances with a yearly rule (`BYMONTH` with an ordinal `BYDAY` or a `BYMONTHDAY`
range, as Outlook, Apple, Google and Lightning write them, `DTSTART` back to 1601) or
with fixed onsets (`DTSTART`, `RDATE`) are taken; a definition with any other rule is
not, and its zone stays unknown. Wall times are compared with onsets in the wall time
before the change (`TZOFFSETFROM`), which is exact away from the changes themselves.

Structural caps (re-check M10 Task 7a, RC7a-1, RC7a-5), far above what producers write
(one month and one weekday per rule, a seven-day `BYMONTHDAY` range, a few hundred
onsets for a zone's history): `MAX_OBSERVANCES`, `MAX_RULED`, `MAX_ONSETS`, and per rule
`MAX_RULE_MONTHS`, `MAX_RULE_DAYS`, `MAX_RULE_MONTHDAYS`. A definition beyond any of them
is refused as `ical.time_zone_too_large`. One `offset_at` is a bisection over the fixed
onsets plus each ruled observance's onsets near the year, and tells `spend` that work:
one unit, and per ruled observance and year asked one unit plus one per month and
list entry (`Observance.year_work`).
"""

import calendar
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import MAXYEAR, MINYEAR, date, datetime, timedelta

from app.modules.calendars.ical import lines, problems
from app.modules.calendars.ical.problems import Skip
from app.modules.calendars.recurrence_rule import Freq, ParsedRule, RuleInvalid, parse_rule

_LARGEST = timedelta.max
# icalendar writes one observance per kind of change over the years it covers; a
# definition with more is not compared.
MAX_OBSERVANCES = 1000
# Producers write a yearly rule for today's changes and maybe a few for earlier ones;
# each is asked again at every wall time compared.
MAX_RULED = 20
MAX_ONSETS = 5000  # every DTSTART and RDATE of a definition
MAX_RULE_MONTHS = 3
MAX_RULE_DAYS = 3  # BYDAY entries
MAX_RULE_MONTHDAYS = 10
_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _free(units: int) -> None:
    pass


class TooLarge(Skip):
    def __init__(self) -> None:
        super().__init__(problems.TIME_ZONE_TOO_LARGE)


@dataclass(frozen=True, slots=True)
class Observance:
    start: datetime  # wall time before the change
    offset_from: timedelta
    offset_to: timedelta
    rule: ParsedRule | None
    rdates: tuple[datetime, ...]
    year_work: int = field(default=0, compare=False)  # what one year's onsets cost

    def __post_init__(self) -> None:
        rule = self.rule
        if rule is not None:
            months = len(rule.bymonth) or 1
            work = 1 + months * (1 + len(rule.byday) + len(rule.bymonthday))
            object.__setattr__(self, "year_work", work)

    def rule_years(self, year: int) -> list[int]:
        """The years whose onsets may come last before a wall time in `year`: the year
        before and `year`, and the last of a rule that ended earlier; years outside 1
        to 9999 have none."""
        rule = self.rule
        if rule is None:
            return []
        years = {year - 1, year}
        if rule.until is not None:
            years.add(rule.until.year)
        if rule.count is not None:
            years.add(self.start.year + (rule.count - 1) * rule.interval)
        # a neighbour's onset stays a datetime
        return sorted([each for each in years if MINYEAR < each < MAXYEAR])

    def onsets_in(self, year: int) -> list[datetime]:
        rule = self.rule
        assert rule is not None
        periods, rest = divmod(year - self.start.year, rule.interval)
        if periods < 0 or rest or (rule.count is not None and periods >= rule.count):
            return []
        found = []
        for month in rule.bymonth or (self.start.month,):
            for day in days_of(rule, year, month, self.start.day):
                onset = datetime.combine(date(year, month, day), self.start.time())
                if onset > self.start and _before_until(rule, onset - self.offset_from):
                    found.append(onset)
        return found


def _before_until(rule: ParsedRule, moment: datetime) -> bool:
    until = rule.until
    if until is None:
        return True
    if isinstance(until, datetime):
        return moment <= until.replace(tzinfo=None)
    return moment.date() <= until


def days_of(rule: ParsedRule, year: int, month: int, start_day: int = 1) -> list[int]:
    """The days of `month` in `year` a yearly rule picks (its start's day without
    BYMONTHDAY or BYDAY); `vtimezone_out` writes rules this reader reads. Found by
    arithmetic: work by the rule's list entries, never by the days of the month."""
    first_weekday = date(year, month, 1).weekday()
    last = _MONTH_DAYS[month - 1] + (month == 2 and calendar.isleap(year))
    if not rule.bymonthday and not rule.byday:
        return [start_day] if start_day <= last else []
    days: list[int] | range = range(1, last + 1)
    if rule.bymonthday:
        days = sorted({d if d > 0 else last + 1 + d for d in rule.bymonthday if abs(d) <= last})
    if not rule.byday:
        return list(days)
    picked: set[int] = set()
    for weekday, ordinal in rule.byday:
        matching: list[int] | range
        if isinstance(days, range):  # every day: the weekday's are a step of seven
            matching = range(1 + (weekday - first_weekday) % 7, last + 1, 7)
        else:
            matching = [d for d in days if (first_weekday + d - 1) % 7 == weekday]
        if ordinal == 0:
            picked.update(matching)
        elif abs(ordinal) <= len(matching):
            picked.add(matching[ordinal - 1] if ordinal > 0 else matching[ordinal])
    return sorted(picked)


@dataclass(frozen=True, slots=True)
class Definition:
    """A VTIMEZONE's offsets: its fixed onsets sorted for a bisection, its ruled
    observances apart (re-check RC7a-5: a look-up never walks every observance)."""

    location: str | None  # X-LIC-LOCATION, a hint only
    fixed: tuple[tuple[datetime, timedelta], ...]  # every DTSTART and RDATE, sorted
    ruled: tuple[Observance, ...]  # observances that follow a rule
    earliest: timedelta  # the offset before the first observance begins

    @classmethod
    def of(cls, observances: tuple[Observance, ...], location: str | None) -> "Definition":
        fixed = sorted((onset, o.offset_to) for o in observances for onset in (o.start, *o.rdates))
        ruled = tuple(o for o in observances if o.rule is not None)
        earliest = min(observances, key=lambda o: o.start).offset_from
        return cls(location, tuple(fixed), ruled, earliest)

    @property
    def size(self) -> int:
        """What building it cost: its onsets and observances."""
        return len(self.fixed) + len(self.ruled)

    def offset_at(self, wall: datetime, spend: Callable[[int], None] = _free) -> timedelta:
        """The offset the definition gives at the wall time `wall`; never raises. The
        work goes to `spend` before it is done."""
        asked = [(o, o.rule_years(wall.year)) for o in self.ruled]
        spend(1 + sum(len(years) * o.year_work for o, years in asked))
        best: tuple[datetime, timedelta] | None = None
        index = bisect_right(self.fixed, (wall, _LARGEST))
        if index:
            best = self.fixed[index - 1]
        for observance, years in asked:
            for year in years:
                try:
                    onsets = observance.onsets_in(year)
                except (ValueError, OverflowError):
                    continue  # a year the rule cannot reach
                for onset in onsets:
                    if onset <= wall and (best is None or onset > best[0]):
                        best = (onset, observance.offset_to)
        return best[1] if best is not None else self.earliest


def definition(component: lines.Component) -> Definition | None:
    """The VTIMEZONE `component` as offsets; None if it cannot be read, `TooLarge` (a
    `Skip`) beyond a cap."""
    children = [c for c in component.children if c.name in ("STANDARD", "DAYLIGHT")]
    if len(children) > MAX_OBSERVANCES:
        raise TooLarge()
    try:
        observances = tuple(_observance(child) for child in children)
    except TooLarge:
        raise
    except (Skip, RuleInvalid, ValueError):
        return None
    if not observances:
        return None
    if sum(o.rule is not None for o in observances) > MAX_RULED:
        raise TooLarge()
    if sum(1 + len(o.rdates) for o in observances) > MAX_ONSETS:
        raise TooLarge()
    location = component.first("X-LIC-LOCATION")
    return Definition.of(observances, location.text.strip() if location else None)


def _observance(child: lines.Component) -> Observance:
    start = _wall(child.first("DTSTART"))
    rules = child.all("RRULE")
    rule = None
    if rules:
        rule = parse_rule(rules[0].raw)
        if len(rules) > 1 or rule.freq is not Freq.YEARLY or rule.bysetpos:
            raise ValueError("a rule the calendar does not compare")
        if (
            len(rule.bymonth) > MAX_RULE_MONTHS
            or len(rule.byday) > MAX_RULE_DAYS
            or len(rule.bymonthday) > MAX_RULE_MONTHDAYS
        ):
            raise TooLarge()
    rdates = tuple(
        value if isinstance(value, datetime) else datetime.combine(value, start.time())
        for prop in child.all("RDATE")
        for value in lines.date_times(prop)
    )
    return Observance(
        start=start,
        offset_from=lines.offset(_required(child, "TZOFFSETFROM")),
        offset_to=lines.offset(_required(child, "TZOFFSETTO")),
        rule=rule,
        rdates=tuple(r.replace(tzinfo=None) for r in rdates),
    )


def _required(child: lines.Component, name: str) -> str:
    prop = child.first(name)
    if prop is None:
        raise ValueError(f"{name} missing")
    return prop.raw


def _wall(prop: lines.Prop | None) -> datetime:
    if prop is None:
        raise ValueError("DTSTART missing")
    value = lines.date_time(prop.raw)
    if not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time())
    return value.replace(tzinfo=None)
