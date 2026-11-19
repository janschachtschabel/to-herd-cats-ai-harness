"""Reading an iCalendar file into event drafts (plan M10 decision 10): lenient, and
whatever it leaves out is counted by code (`problems`), never raised.

The VEVENTs of every VCALENDAR in the data are grouped by UID in the order of their
first appearance: the one without RECURRENCE-ID is the series, the others replace one
of its occurrences each (an override with `STATUS:CANCELLED` deletes it instead, as an
EXDATE). Up to `limit` events are read; every group after that counts as
`ical.over_limit` without being parsed. Times: `times`; zones: `zones`; texts,
attendees and alarms: `content`.
"""

from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime

from app.modules.calendars import recurrence, recurrence_ids, zones
from app.modules.calendars.ical import content, lines, problems, times
from app.modules.calendars.ical.budget import Budget, OverBudget, check_cost
from app.modules.calendars.ical.drafts import (
    MAX_OVERRIDES,
    MAX_UID,
    EventDraft,
    OverrideDraft,
    Status,
)
from app.modules.calendars.ical.problems import Skip
from app.modules.calendars.ical.zones import Resolver
from app.modules.calendars.recurrence import Series, SeriesInvalid


@dataclass(frozen=True, slots=True)
class Parsed:
    events: list[EventDraft]
    problems: Counter[str]


@dataclass(slots=True)
class _Group:
    master: lines.Component | None = None
    overrides: list[lines.Component] = field(default_factory=list)

    def parts(self) -> list[lines.Component]:
        return ([self.master] if self.master else []) + self.overrides


def parse(data: bytes, *, default_zone: str, limit: int) -> Parsed:
    """The events of `data`, read in the calendar's zone `default_zone` (for floating
    times; an unknown zone is the caller's error: `zones.ZoneUnknown`)."""
    zones.zone(default_zone)
    try:
        tops, found = lines.read(data)
    except (ValueError, ArithmeticError, LookupError, RecursionError):  # the last guard
        return Parsed([], Counter({problems.UNREADABLE: 1}))
    if not any(top.name == "VCALENDAR" for top in tops):
        return Parsed([], Counter({problems.UNREADABLE: 1}))
    timezones: dict[str, lines.Component] = {}
    events: list[lines.Component] = []
    # the components of every VCALENDAR, and those found beside one (after an early
    # END:VCALENDAR, R7a-8)
    children = [c for top in tops for c in (top.children if top.name == "VCALENDAR" else [top])]
    for child in children:
        if child.name == "VEVENT":
            events.append(child)
        elif child.name == "VTIMEZONE":
            tzid = child.first("TZID")
            if tzid is not None:  # TEXT: some write it escaped (`\,`), some not
                timezones.setdefault(tzid.text.strip(), child)
                timezones.setdefault(tzid.raw.strip(), child)
        else:
            found[problems.NOT_AN_EVENT] += 1
    resolver = Resolver(timezones)
    budget = Budget()
    drafts: list[EventDraft] = []
    for uid, group in _groups(events, found).items():
        if len(drafts) >= limit:
            found[problems.OVER_LIMIT] += 1
            continue
        if budget.exhausted:
            found[problems.OVER_BUDGET] += 1
            continue
        if group.master is None:  # occurrences without their series (RFC 4791 4.1)
            found[problems.OVERRIDE_ORPHANED] += len(group.overrides)
            continue
        notes: Counter[str] = Counter()
        try:
            frame = times.Frame.of(default_zone, resolver, group.parts(), budget)
            drafts.append(_draft(uid, group, frame, notes))
            found.update(notes)
        except Skip as skip:
            found[skip.code] += 1
        except (ValueError, ArithmeticError, LookupError, RecursionError):
            found[problems.EVENT_UNREADABLE] += 1  # the last guard: never raise for a file
        found[problems.LINE_UNREADABLE] += sum(_broken(part) for part in group.parts())
    return Parsed(drafts, +found)


def _groups(events: list[lines.Component], found: Counter[str]) -> dict[str, _Group]:
    groups: dict[str, _Group] = {}
    for event in events:
        written = event.quick("UID")
        uid = lines.one_word(written.text) if written else ""
        if not uid or len(uid) > MAX_UID:
            found[problems.UID_MISSING] += 1
            continue
        group = groups.setdefault(uid, _Group())
        if event.quick("RECURRENCE-ID") is not None:
            group.overrides.append(event)
        elif group.master is None:
            group.master = event
        else:
            found[problems.DUPLICATE_UID] += 1
    return groups


def _broken(part: lines.Component) -> int:
    count, todo = 0, [part]
    while todo:
        each = todo.pop()
        count += each.broken
        todo.extend(each.children)
    return count


def _draft(uid: str, group: _Group, frame: times.Frame, notes: Counter[str]) -> EventDraft:
    master = group.master
    assert master is not None  # orphaned overrides are counted by `parse`
    begin, series = _series(master, frame, notes, single=False)
    parts = group.overrides[:MAX_OVERRIDES]
    notes[problems.OVER_LIMIT] += len(group.overrides) - len(parts)
    ids = _recurrence_ids(parts, begin, series, frame, notes)
    overrides: dict[datetime, OverrideDraft] = {}
    cancelled: set[datetime] = set()
    for part, recurrence_id in zip(parts, ids, strict=True):
        if recurrence_id is None:
            continue
        try:
            override = _override(part, recurrence_id, frame, notes)
        except OverBudget:
            raise
        except Skip as skip:
            notes[skip.code] += 1
            continue
        if recurrence_id in overrides or recurrence_id in cancelled:
            notes[problems.DUPLICATE_UID] += 1
        elif override is None:
            cancelled.add(recurrence_id)
        else:
            overrides[recurrence_id] = override
    exdates = (set(series.exdates) | cancelled) - set(overrides)
    series = replace(series, exdates=tuple(sorted(exdates)))
    return EventDraft(
        uid=uid,
        series=series,
        content=content.read(master, all_day=series.all_day, notes=notes),
        organiser=content.organiser(master),
        overrides=tuple(overrides[key] for key in sorted(overrides)),
        alarms=content.alarms(master, series.duration, notes),
    )


def _series(
    part: lines.Component, frame: times.Frame, notes: Counter[str], *, single: bool
) -> tuple[times.Start, Series]:
    rules = [] if single else part.all("RRULE")
    added = [] if single else part.all("RDATE")
    if len(rules) > 1 or (not single and part.first("EXRULE") is not None):
        raise Skip(problems.RRULE_UNSUPPORTED)
    begin = times.start(part, frame, recurring=bool(rules or added))
    duration = times.length(part, begin, frame)
    removed = [] if single else part.all("EXDATE")
    try:
        rule = recurrence.check_rule(times.until(rules[0].raw, begin, frame)) if rules else None
        series = Series(
            start=begin.wall,
            duration=duration,
            tzid=begin.tzid,
            all_day=begin.all_day,
            rrule=rule,
            rdates=tuple(sorted({w for prop in added for w in times.walls(prop, begin, frame)})),
        )
    except SeriesInvalid as refused:
        raise Skip(problems.FROM_SERIES.get(refused.code, problems.TIME_INVALID)) from None
    parsed_rule = series.rule
    if parsed_rule is not None:
        first: datetime | None = None
        try:
            first = recurrence.check_series(series)
        except SeriesInvalid:
            notes[problems.RRULE_NEVER_MATCHES] = 1
            series = replace(series, rrule=None)
        frame.budget.spend(check_cost(parsed_rule, series.start, first))
    if removed:
        values = [m for prop in removed for m in times.moments(prop, begin, frame)]
        found = _occurrences(series, values, frame)
        exdates = {found.get(value, value[0]) for value in values}
        series = replace(series, exdates=tuple(sorted(exdates)))
    return begin, series


def _recurrence_ids(
    parts: list[lines.Component],
    begin: times.Start,
    series: Series,
    frame: times.Frame,
    notes: Counter[str],
) -> list[datetime | None]:
    """Each override's recurrence id as the series names it, or None (counted): the
    series is expanded once for all of them (R7a-4)."""
    values: list[tuple[datetime, datetime | None] | None] = []
    for part in parts:
        written = part.first("RECURRENCE-ID")
        try:
            if written is None:
                raise Skip(problems.TIME_INVALID)
            if (written.param("RANGE") or "").upper() == "THISANDFUTURE":
                raise Skip(problems.OVERRIDE_UNSUPPORTED)
            found = times.moments(written, begin, frame)
            if not found:
                raise Skip(problems.TIME_INVALID)
            values.append(found[0])
        except OverBudget:
            raise
        except Skip as skip:
            notes[skip.code] += 1
            values.append(None)
    named = _occurrences(series, [v for v in values if v is not None], frame)
    ids: list[datetime | None] = []
    for value in values:
        if value is not None and value not in named:
            notes[problems.OVERRIDE_UNMATCHED] += 1
        ids.append(named.get(value) if value is not None else None)
    return ids


def _occurrences(
    series: Series, values: list[tuple[datetime, datetime | None]], frame: times.Frame
) -> dict[tuple[datetime, datetime | None], datetime]:
    """The recurrence id each value (a wall time, and the instant it was read from, if
    any) names: the wall time if the series has it, else the occurrence that starts at
    that instant (one in a gap, R7a-6)."""
    walls = recurrence_ids.named(series, (wall for wall, _ in values), frame.budget.spend)
    found = {value: value[0] for value in values if value[0] in walls}
    moments = {instant for wall, instant in values if instant is not None and wall not in walls}
    if moments:
        at = recurrence_ids.ids_at(series, moments, frame.budget.spend)
        for value in values:
            instant = value[1]
            if value not in found and instant is not None and instant in at:
                found[value] = at[instant]
    return found


def _override(
    part: lines.Component, recurrence_id: datetime, frame: times.Frame, notes: Counter[str]
) -> OverrideDraft | None:
    if content.status(part) is Status.CANCELLED:
        return None
    _, own = _series(part, frame, notes, single=True)
    return OverrideDraft(recurrence_id, own, content.read(part, all_day=own.all_day, notes=notes))
