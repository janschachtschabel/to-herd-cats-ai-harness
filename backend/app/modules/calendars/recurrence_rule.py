"""An RRULE as the calendar takes it (plan M10 decision 6): parsed, checked and written
in one canonical form; pure, no library.

Taken: `FREQ` from `DAILY` up, `INTERVAL`, `COUNT` (at most 5,000) or `UNTIL`, `BYDAY`
(with an ordinal for `MONTHLY`/`YEARLY` only), `BYMONTHDAY`, `BYMONTH`, `BYSETPOS`,
`WKST`. Refused with `event.rrule_unsupported`: what RFC 5545 allows but the calendar
does not (`SECONDLY`/`MINUTELY`/`HOURLY`, `BYHOUR`/`BYMINUTE`/`BYSECOND`, `BYYEARDAY`,
`BYWEEKNO`, a larger `COUNT` or `INTERVAL`, a floating `UNTIL`); with
`event.rrule_invalid`: what is no rule (unknown or repeated parts, values out of
range, `COUNT` with `UNTIL`, a day of the month no month has).
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from functools import lru_cache

MAX_CHARS = 500
MAX_COUNT = 5000
MAX_INTERVAL = 1000
WEEKDAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
# The longest each month can be (February in a leap year).
_MONTH_DAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_UNSUPPORTED_PARTS = frozenset({"BYSECOND", "BYMINUTE", "BYHOUR", "BYYEARDAY", "BYWEEKNO"})
_PARTS = frozenset(
    {"FREQ", "INTERVAL", "COUNT", "UNTIL", "BYMONTH", "BYMONTHDAY", "BYDAY", "BYSETPOS", "WKST"}
)
# ASCII digits only: `\d` and `str.isdigit()` take any Unicode digit ("٣", "²").
_NUMBER = re.compile(r"[+-]?[0-9]{1,4}")
_WHOLE = re.compile(r"[0-9]+")
_DAY = re.compile(r"([+-]?[0-9]{1,2})?(MO|TU|WE|TH|FR|SA|SU)")
_UNTIL = re.compile(r"[0-9]{8}(T[0-9]{6}Z?)?")


class SeriesInvalid(ValueError):
    """A series that cannot be taken; `code` is the API's error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RuleInvalid(SeriesInvalid):
    """`code` is `event.rrule_invalid` or `event.rrule_unsupported`."""


class Freq(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


@dataclass(frozen=True, slots=True)
class ParsedRule:
    freq: Freq
    interval: int = 1
    count: int | None = None
    until: date | datetime | None = None  # a date, or an instant in UTC
    bymonth: tuple[int, ...] = ()
    bymonthday: tuple[int, ...] = ()
    byday: tuple[tuple[int, int], ...] = ()  # (weekday 0 = MO, ordinal; 0: none)
    bysetpos: tuple[int, ...] = ()
    wkst: int = 0

    @property
    def text(self) -> str:
        parts = [f"FREQ={self.freq}"]
        if isinstance(self.until, datetime):
            parts.append(f"UNTIL={self.until:%Y%m%dT%H%M%SZ}")
        elif self.until is not None:
            parts.append(f"UNTIL={self.until:%Y%m%d}")
        if self.count is not None:
            parts.append(f"COUNT={self.count}")
        if self.interval != 1:
            parts.append(f"INTERVAL={self.interval}")
        if self.bymonth:
            parts.append("BYMONTH=" + ",".join(map(str, self.bymonth)))
        if self.bymonthday:
            parts.append("BYMONTHDAY=" + ",".join(map(str, self.bymonthday)))
        if self.byday:
            days = (f"{n or ''}{WEEKDAYS[day]}" for day, n in self.byday)
            parts.append("BYDAY=" + ",".join(days))
        if self.bysetpos:
            parts.append("BYSETPOS=" + ",".join(map(str, self.bysetpos)))
        if self.wkst:
            parts.append(f"WKST={WEEKDAYS[self.wkst]}")
        return ";".join(parts)


def check_rule(text: str) -> str:
    """The rule `text` in canonical form; `RuleInvalid` if it cannot be taken."""
    return parse_rule(text).text


def _invalid() -> RuleInvalid:
    return RuleInvalid("event.rrule_invalid")


def _unsupported() -> RuleInvalid:
    return RuleInvalid("event.rrule_unsupported")


def _split(text: str) -> dict[str, str]:
    body = text.strip()
    if body.upper().startswith("RRULE:"):
        body = body[len("RRULE:") :]
    if not body or len(body) > MAX_CHARS:
        raise _invalid()
    parts: dict[str, str] = {}
    for item in body.split(";"):
        name, sep, value = item.partition("=")
        name = name.strip().upper()
        if not sep or not value or name in parts:
            raise _invalid()
        parts[name] = value.strip().upper()
    if set(parts) & _UNSUPPORTED_PARTS:
        raise _unsupported()
    if set(parts) - _PARTS:
        raise _invalid()
    return parts


def _numbers(value: str, low: int, high: int) -> tuple[int, ...]:
    found: set[int] = set()
    for item in value.split(","):
        if not _NUMBER.fullmatch(item) or not low <= abs(int(item)) <= high:
            raise _invalid()
        found.add(int(item))
    return tuple(sorted(found))


def _number(value: str, high: int) -> int:
    if not _WHOLE.fullmatch(value) or int(value) < 1:
        raise _invalid()
    if int(value) > high:
        raise _unsupported()
    return int(value)


def _until(value: str) -> date | datetime:
    if not _UNTIL.fullmatch(value):
        raise _invalid()
    try:
        if len(value) == 8:
            return datetime.strptime(value, "%Y%m%d").date()
        if len(value) == 16 and value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        datetime.strptime(value, "%Y%m%dT%H%M%S")
    except ValueError:
        raise _invalid() from None
    raise _unsupported()  # a floating date-time: the calendar has no floating starts


def _days(value: str, freq: Freq, in_months: bool) -> tuple[tuple[int, int], ...]:
    limit = 5 if freq is Freq.MONTHLY or in_months else 53
    found: set[tuple[int, int]] = set()
    for item in value.split(","):
        match = _DAY.fullmatch(item)
        if match is None:
            raise _invalid()
        ordinal = int(match.group(1) or 0)
        if match.group(1) and (freq in (Freq.DAILY, Freq.WEEKLY) or not 1 <= abs(ordinal) <= limit):
            raise _invalid()
        found.add((WEEKDAYS.index(match.group(2)), ordinal))
    return tuple(sorted(found))


def _weekday(value: str) -> int:
    if value not in WEEKDAYS:
        raise _invalid()
    return WEEKDAYS.index(value)


@lru_cache(maxsize=4096)
def parse_rule(text: str) -> ParsedRule:
    parts = _split(text)
    freq_name = parts.get("FREQ", "")
    if freq_name in ("SECONDLY", "MINUTELY", "HOURLY"):
        raise _unsupported()
    if freq_name not in Freq.__members__:
        raise _invalid()
    freq = Freq(freq_name)
    if "COUNT" in parts and "UNTIL" in parts:
        raise _invalid()
    bymonth = _numbers(parts["BYMONTH"], 1, 12) if "BYMONTH" in parts else ()
    if any(month < 0 for month in bymonth):
        raise _invalid()
    rule = ParsedRule(
        freq=freq,
        interval=_number(parts["INTERVAL"], MAX_INTERVAL) if "INTERVAL" in parts else 1,
        count=_number(parts["COUNT"], MAX_COUNT) if "COUNT" in parts else None,
        until=_until(parts["UNTIL"]) if "UNTIL" in parts else None,
        bymonth=bymonth,
        bymonthday=_numbers(parts["BYMONTHDAY"], 1, 31) if "BYMONTHDAY" in parts else (),
        byday=_days(parts["BYDAY"], freq, bool(bymonth)) if "BYDAY" in parts else (),
        bysetpos=_numbers(parts["BYSETPOS"], 1, 366) if "BYSETPOS" in parts else (),
        wkst=_weekday(parts["WKST"]) if "WKST" in parts else 0,
    )
    _check_combination(rule)
    return rule


def _check_combination(rule: ParsedRule) -> None:
    if rule.bymonthday and rule.freq is Freq.WEEKLY:
        raise _invalid()  # RFC 5545 3.3.10: BYMONTHDAY MUST NOT come with WEEKLY
    if rule.bysetpos and not (rule.bymonth or rule.bymonthday or rule.byday):
        raise _invalid()  # BYSETPOS selects from what another BYxxx part gives
    if rule.bymonthday:
        months = rule.bymonth or tuple(range(1, 13))
        if not any(abs(day) <= _MONTH_DAYS[m - 1] for m in months for day in rule.bymonthday):
            raise _invalid()  # 30 February: no month has the day
