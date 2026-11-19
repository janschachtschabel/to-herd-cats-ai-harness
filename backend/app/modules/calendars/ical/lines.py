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

from icalendar.parser import Contentline, Contentlines
from icalendar.parser.property import unescape_backslash

from app.modules.calendars.ical import problems
from app.modules.calendars.ical.problems import Skip

# ASCII digits only; seconds up to 60 (a leap second, read as 59).
_DATE_TIME = re.compile(r"([0-9]{4})([0-9]{2})([0-9]{2})(?:T([0-9]{2})([0-9]{2})([0-9]{2})(Z)?)?")
# RFC 5545 3.3.6: weeks or days (nominal) and a time part (exact).
_DURATION = re.compile(
    r"([+-])?P(?:([0-9]{1,6})W)?(?:([0-9]{1,6})D)?(?:T(?:([0-9]{1,6})H)?(?:([0-9]{1,6})M)?(?:([0-9]{1,6})S)?)?"
)
_OFFSET = re.compile(r"([+-])([0-9]{2})([0-9]{2})([0-9]{2})?")
# C0 controls but tab and line feed, and DEL: never in a text (Postgres takes no NUL).
_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
# RFC 5545 3.1: a line break followed by a space or tab continues the line.
_FOLD = re.compile(rb"\r?\n[ \t]")
_FOLD_TEXT = re.compile(r"\r?\n[ \t]")
# A calendar needs three levels (VCALENDAR, VEVENT or VTIMEZONE, VALARM or an
# observance); a little more for producers' own components, nothing deeper.
MAX_DEPTH = 6


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
    return Prop(str(name).upper(), flat, str(raw), unescape_backslash(str(raw)))


def read(data: bytes) -> tuple[list[Component], Counter[str]]:
    """The top-level components of `data` and what could not be read of it, in one pass
    over the lines (work linear in the data, R7a-2):

    - an END without its BEGIN, a component that never ends and components nested
      deeper than `MAX_DEPTH` count as `ical.unreadable` (once); the latter two are
      dropped;
    - a `BEGIN:VEVENT` while a VEVENT is open closes that one first, so one missing
      `END:VEVENT` does not swallow every later event (R7a-8);
    - text that is no UTF-8 (or UTF-16 with its byte order mark) is read with
      replacement characters and counts as `ical.text_replaced` (once).
    """
    text, found = _decode(data)
    try:
        lines = Contentlines.from_ical(text)  # type: ignore[no-untyped-call]
    except ValueError:
        return [], Counter({problems.UNREADABLE: 1})
    tops: list[Component] = []
    stack: list[Component] = []
    open_names: Counter[str] = Counter()  # how many of each name `stack` holds
    ignored = 0  # depth inside components dropped for nesting too deep

    def close(name: str) -> None:
        while True:
            done = stack.pop()
            open_names[done.name] -= 1
            if done.name == name:
                (stack[-1].children if stack else tops).append(done)
                return
            found[problems.UNREADABLE] = 1  # a component inside that never ended

    for line in lines:
        head = line[:6].upper()
        if head == "BEGIN:":
            name = line[6:].strip().upper()
            if ignored or len(stack) >= MAX_DEPTH:
                ignored += 1
                found[problems.UNREADABLE] = 1
                continue
            if name == "VEVENT" and open_names["VEVENT"]:
                close("VEVENT")
                found[problems.UNREADABLE] = 1
            stack.append(Component(name))
            open_names[name] += 1
        elif head[:4] == "END:":
            if ignored:
                ignored -= 1
                continue
            name = line[4:].strip().upper()
            if not open_names[name]:
                found[problems.UNREADABLE] = 1  # an END without its BEGIN
                continue
            close(name)
        elif ignored:
            continue
        elif stack:
            stack[-1].lines.append(line)
        elif line.strip():
            found[problems.LINE_UNREADABLE] += 1
    if stack:
        found[problems.UNREADABLE] = 1
    return tops, found


def _decode(data: bytes) -> tuple[str, Counter[str]]:
    """`data` as text: UTF-16 by its byte order mark, otherwise UTF-8 (RFC 5545 3.1),
    unfolded on the octets first, so a fold between the octets of one character
    joins them again (R7a-7)."""
    found: Counter[str] = Counter()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = data.decode("utf-16", errors="replace")
        if "\ufffd" in text:
            found[problems.TEXT_REPLACED] = 1
        return _FOLD_TEXT.sub("", text).removeprefix("\ufeff"), found
    unfolded = _FOLD.sub(b"", data)
    try:
        text = unfolded.decode("utf-8")
    except UnicodeDecodeError:
        text = unfolded.decode("utf-8", errors="replace")
        found[problems.TEXT_REPLACED] = 1
    return text.removeprefix("\ufeff"), found


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


def duration(value: str) -> tuple[int, timedelta]:
    """A DURATION as its nominal days (weeks count seven) and its exact time, both with
    the duration's sign: `PT36H` is 36 hours, `P1DT12H` a day and 12 hours."""
    match = _DURATION.fullmatch(value.strip().upper())
    if (
        match is None
        or match.group(0).rstrip("T") in ("P", "+P", "-P")
        or value.strip().endswith("T")
    ):
        raise Skip(problems.TIME_INVALID)
    sign, weeks, days, hours, minutes, seconds = match.groups()
    whole = int(weeks or 0) * 7 + int(days or 0)
    exact = timedelta(hours=int(hours or 0), minutes=int(minutes or 0), seconds=int(seconds or 0))
    return (-whole, -exact) if sign == "-" else (whole, exact)


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
    return valid_address(prop.raw[7:].strip())


def valid_address(text: str) -> str | None:
    """`text` if it is one address (`local@domain`, no space or control character, at
    most 320 characters), else None."""
    local, at, domain = text.partition("@")
    if not (local and at and domain) or len(text) > 320:
        return None
    if any(c.isspace() or c < " " or c == "\x7f" for c in text):
        return None
    return text


def one_line(text: str) -> str:
    """`text` without control characters and with its white space runs as one space
    (a name)."""
    return " ".join(clean(text).split())
