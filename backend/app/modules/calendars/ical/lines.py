"""The components of an iCalendar file and the values of their properties (RFC 5545
3.1 to 3.3), read leniently: `icalendar` unfolds the lines and splits each into name,
parameters and value; nothing here resolves a zone or builds a series.

A property is parsed only when it is asked for, so counting the events beyond a limit
costs little more than finding their `BEGIN`, `END` and `UID` lines.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from icalendar import vDuration
from icalendar.parser import Contentline, Contentlines

from app.modules.calendars.ical import problems
from app.modules.calendars.ical.problems import Skip

# ASCII digits only; seconds up to 60 (a leap second, read as 59).
_DATE_TIME = re.compile(r"([0-9]{4})([0-9]{2})([0-9]{2})(?:T([0-9]{2})([0-9]{2})([0-9]{2})(Z)?)?")
_OFFSET = re.compile(r"([+-])([0-9]{2})([0-9]{2})([0-9]{2})?")
# C0 controls but tab and line feed, and DEL: never in a text (Postgres takes no NUL).
_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


@dataclass(frozen=True, slots=True)
class Prop:
    name: str  # upper case
    params: dict[str, str]  # upper-case names; a list keeps its first value
    raw: str  # the value as written
    text: str  # the value with TEXT escapes resolved

    def param(self, name: str) -> str | None:
        return self.params.get(name)


@dataclass(slots=True)
class Component:
    name: str  # upper case
    lines: list[Contentline] = field(default_factory=list)
    children: list["Component"] = field(default_factory=list)
    _props: list[Prop] | None = None
    broken: int = 0  # lines that could not be split

    def props(self) -> list[Prop]:
        if self._props is None:
            self._props = []
            for line in self.lines:
                try:
                    self._props.append(_prop(line))
                except ValueError:
                    self.broken += 1
        return self._props

    def all(self, name: str) -> list[Prop]:
        return [prop for prop in self.props() if prop.name == name]

    def first(self, name: str) -> Prop | None:
        return next((prop for prop in self.props() if prop.name == name), None)

    def quick(self, name: str) -> Prop | None:
        """The first property `name`, parsing only the lines that may be it."""
        if self._props is not None:
            return self.first(name)
        for line in self.lines:
            if line[: len(name)].upper() == name and line[len(name) : len(name) + 1] in (":", ";"):
                try:
                    return _prop(line)
                except ValueError:
                    return None
        return None


def _prop(line: Contentline) -> Prop:
    name, params, raw = line.raw_parts()
    flat = {
        str(key).upper(): str(value[0] if isinstance(value, list) and value else value)
        for key, value in params.items()
    }
    return Prop(str(name).upper(), flat, str(raw), line.parts()[2])


def read(data: bytes) -> tuple[list[Component], Counter[str]]:
    """The top-level components of `data` and what could not be read of it. A component
    that never ends, or an END without its BEGIN, counts as `ical.unreadable` (once);
    such a component is dropped."""
    found: Counter[str] = Counter()
    text = data.decode("utf-8", errors="replace").removeprefix("﻿")
    try:
        lines = Contentlines.from_ical(text)  # type: ignore[no-untyped-call]
    except ValueError:
        return [], Counter({problems.UNREADABLE: 1})
    tops: list[Component] = []
    stack: list[Component] = []
    for line in lines:
        head = line[:6].upper()
        if head == "BEGIN:":
            stack.append(Component(line[6:].strip().upper()))
        elif head[:4] == "END:":
            name = line[4:].strip().upper()
            if not any(open_.name == name for open_ in stack):
                found[problems.UNREADABLE] = 1  # an END without its BEGIN
                continue
            while stack[-1].name != name:
                stack.pop()  # a component inside that never ended
                found[problems.UNREADABLE] = 1
            done = stack.pop()
            (stack[-1].children if stack else tops).append(done)
        elif stack:
            stack[-1].lines.append(line)
        elif line.strip():
            found[problems.LINE_UNREADABLE] += 1
    if stack:
        found[problems.UNREADABLE] = 1
    return tops, found


def clean(text: str) -> str:
    return _CONTROLS.sub("", text)


def date_time(value: str) -> date | datetime:
    """A DATE (`date`), a floating or zoned DATE-TIME (naive) or one in UTC (aware)."""
    match = _DATE_TIME.fullmatch(value.strip().upper())
    if match is None:
        raise Skip(problems.TIME_INVALID)
    year, month, day, hour, minute, second, utc = match.groups()
    try:
        if hour is None:
            return date(int(year), int(month), int(day))
        moment = datetime(
            int(year), int(month), int(day), int(hour), int(minute), min(int(second), 59)
        )
    except ValueError:
        raise Skip(problems.TIME_INVALID) from None
    return moment.replace(tzinfo=UTC) if utc else moment


def date_times(prop: Prop) -> list[date | datetime]:
    """The values of a property that may list several (RDATE, EXDATE); a PERIOD gives
    its start; `VALUE=DATE` gives dates even where a time is written."""
    values = [date_time(item.split("/", 1)[0]) for item in prop.raw.split(",") if item.strip()]
    if (prop.param("VALUE") or "").upper() == "DATE":
        return [value.date() if isinstance(value, datetime) else value for value in values]
    return values


def duration(value: str) -> timedelta:
    try:
        found = vDuration.from_ical(value.strip())  # type: ignore[no-untyped-call]
    except (ValueError, TypeError):
        raise Skip(problems.TIME_INVALID) from None
    if not isinstance(found, timedelta):
        raise Skip(problems.TIME_INVALID)
    return found


def offset(value: str) -> timedelta:
    match = _OFFSET.fullmatch(value.strip())
    if match is None:
        raise Skip(problems.TIME_ZONE_UNKNOWN)
    sign, hours, minutes, seconds = match.groups()
    size = timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds or 0))
    return -size if sign == "-" else size


def address(prop: Prop | None) -> str | None:
    """The address of a `mailto:` value (ORGANIZER, ATTENDEE), as written."""
    if prop is None or prop.raw[:7].lower() != "mailto:":
        return None
    found = prop.raw[7:].strip()
    local, at, domain = found.partition("@")
    if not (local and at and domain) or any(c.isspace() for c in found) or len(found) > 320:
        return None
    return clean(found)
