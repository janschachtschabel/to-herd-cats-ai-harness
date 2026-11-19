"""The offsets a file's VTIMEZONE gives (RFC 5545 3.6.5), to compare with `tzdata`
(`zones`); never used to place an event itself.

Observances with a yearly rule (`BYMONTH` with an ordinal `BYDAY` or a `BYMONTHDAY`
range, as Outlook, Apple, Google and Lightning write them, `DTSTART` back to 1601) or
with fixed onsets (`DTSTART`, `RDATE`) are taken; a definition with any other rule is
not, and its zone stays unknown. Wall times are compared with onsets in the wall time
before the change (`TZOFFSETFROM`), which is exact away from the changes themselves.
"""

import calendar
from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import MAXYEAR, MINYEAR, date, datetime, timedelta

from app.modules.calendars.ical import lines
from app.modules.calendars.ical.problems import Skip
from app.modules.calendars.recurrence_rule import Freq, ParsedRule, RuleInvalid, parse_rule

_LARGEST = timedelta.max
# icalendar writes one observance per kind of change over the years it covers; a
# definition with more is not compared.
MAX_OBSERVANCES = 1000
# Producers write a yearly rule for today's changes and maybe a few for earlier ones;
# each is asked again at every wall time compared.
MAX_RULED = 20


@dataclass(frozen=True, slots=True)
class Observance:
    start: datetime  # wall time before the change
    offset_from: timedelta
    offset_to: timedelta
    rule: ParsedRule | None
    rdates: tuple[datetime, ...]

    def rule_onsets_near(self, year: int) -> Iterator[datetime]:
        """The rule's onsets in the years before and of `year`, and the last ones of a
        rule that ended earlier; years outside 1 to 9999 have none."""
        rule = self.rule
        if rule is None:
            return
        years = {year - 1, year}
        if rule.until is not None:
            years.add(rule.until.year)
        if rule.count is not None:
            years.add(self.start.year + (rule.count - 1) * rule.interval)
        for each in sorted(years):
            if MINYEAR < each < MAXYEAR:  # a neighbour's onset stays a datetime
                yield from self._onsets_in(rule, each)

    def _onsets_in(self, rule: ParsedRule, year: int) -> Iterator[datetime]:
        periods, rest = divmod(year - self.start.year, rule.interval)
        if periods < 0 or rest or (rule.count is not None and periods >= rule.count):
            return
        for month in rule.bymonth or (self.start.month,):
            for day in _days(rule, year, month, self.start.day):
                onset = datetime.combine(date(year, month, day), self.start.time())
                if onset > self.start and _before_until(rule, onset - self.offset_from):
                    yield onset


def _before_until(rule: ParsedRule, moment: datetime) -> bool:
    until = rule.until
    if until is None:
        return True
    if isinstance(until, datetime):
        return moment <= until.replace(tzinfo=None)
    return moment.date() <= until


def _days(rule: ParsedRule, year: int, month: int, start_day: int) -> list[int]:
    last = calendar.monthrange(year, month)[1]
    if not rule.bymonthday and not rule.byday:
        return [start_day] if start_day <= last else []
    days = list(range(1, last + 1))
    if rule.bymonthday:
        wanted = {d if d > 0 else last + 1 + d for d in rule.bymonthday}
        days = [d for d in days if d in wanted]
    if not rule.byday:
        return days
    picked: set[int] = set()
    for weekday, ordinal in rule.byday:
        matching = [d for d in days if date(year, month, d).weekday() == weekday]
        if ordinal == 0:
            picked.update(matching)
        elif abs(ordinal) <= len(matching):
            picked.add(matching[ordinal - 1] if ordinal > 0 else matching[ordinal])
    return sorted(picked)


@dataclass(frozen=True, slots=True)
class Definition:
    observances: tuple[Observance, ...]
    location: str | None  # X-LIC-LOCATION, a hint only
    fixed: tuple[tuple[datetime, timedelta], ...] = ()  # every DTSTART and RDATE, sorted

    @classmethod
    def of(cls, observances: tuple[Observance, ...], location: str | None) -> "Definition":
        fixed = sorted((onset, o.offset_to) for o in observances for onset in (o.start, *o.rdates))
        return cls(observances, location, tuple(fixed))

    @property
    def ruled(self) -> int:
        """How many observances follow a rule: the work of one `offset_at`."""
        return sum(o.rule is not None for o in self.observances)

    def offset_at(self, wall: datetime) -> timedelta:
        """The offset the definition gives at the wall time `wall`; never raises."""
        best: tuple[datetime, timedelta] | None = None
        index = bisect_right(self.fixed, (wall, _LARGEST))
        if index:
            best = self.fixed[index - 1]
        for observance in self.observances:
            try:
                onsets = list(observance.rule_onsets_near(wall.year))
            except (ValueError, OverflowError):
                continue  # a year the rule cannot reach
            for onset in onsets:
                if onset <= wall and (best is None or onset > best[0]):
                    best = (onset, observance.offset_to)
        if best is not None:
            return best[1]
        return min(self.observances, key=lambda o: o.start).offset_from


def definition(component: lines.Component) -> Definition | None:
    """The VTIMEZONE `component` as offsets; None if it cannot be read."""
    try:
        observances = tuple(
            _observance(child)
            for child in component.children
            if child.name in ("STANDARD", "DAYLIGHT")
        )
    except (Skip, RuleInvalid, ValueError):
        return None
    if not observances or len(observances) > MAX_OBSERVANCES:
        return None
    if sum(o.rule is not None for o in observances) > MAX_RULED:
        return None
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
