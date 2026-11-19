"""Structural caps on what one file may make the reader do (re-check M10 Task 7a,
RC7a-1 to RC7a-5): where the work is done inside C calls (`str.join`, sets, sorting)
or grows with a part's size, the part is capped, so a count of Python calls stays a
faithful measure of the work. Each refusal is counted under an `ical.*` code."""

import calendar
import random
from collections import Counter
from datetime import date, datetime

import pytest

from app.modules.calendars.ical import lines, reading, vtimezone, zones
from app.modules.calendars.ical.problems import Skip
from app.modules.calendars.recurrence_rule import ParsedRule, RuleInvalid, parse_rule


def _calendar(*parts: str) -> bytes:
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "".join(parts) + "END:VCALENDAR\r\n").encode()


def _event(uid: str, body: str) -> str:
    return f"BEGIN:VEVENT\r\nUID:{uid}\r\n{body}\r\nEND:VEVENT\r\n"


def _parse(data: bytes) -> reading.Parsed:
    return reading.parse(data, default_zone="Europe/Berlin", limit=5000)


def test_a_globally_unique_tzid_resolves_by_its_last_parts() -> None:
    assert zones.by_name("/mozilla.org/20050126_1/America/New_York") == "America/New_York"
    assert zones.by_name("/x/y/America/Argentina/Buenos_Aires") == "America/Argentina/Buenos_Aires"
    assert zones.by_name("/citadel.org/20190914_1/Europe/Berlin/") == "Europe/Berlin"


def test_a_tzid_beyond_its_length_or_parts_is_never_looked_up() -> None:
    longest = "/" + "a" * (zones.MAX_TZID - 15) + "/Europe/Berlin"
    assert len(longest) == zones.MAX_TZID
    assert zones.by_name(longest) == "Europe/Berlin"
    assert zones.by_name("/x" + longest) is None
    eight = "/a/b/c/d/e/f/Europe/Berlin"
    assert zones.by_name(eight) == "Europe/Berlin"
    assert zones.by_name("/z" + eight) is None


def test_an_event_in_a_tzid_beyond_the_caps_is_counted_as_too_large() -> None:
    too_long = "/" + "a" * zones.MAX_TZID + "/Europe/Berlin"
    too_many = "/" + "a/" * zones.MAX_TZID_SEGMENTS + "Europe/Berlin"
    parsed = _parse(
        _calendar(
            _event("a", f"DTSTART;TZID={too_long}:20260101T100000"),
            _event("b", f"DTSTART;TZID={too_many}:20260101T100000"),
            _event("c", "DTSTART;TZID=/a/Europe/Berlin:20260101T100000"),
        )
    )
    assert [e.uid for e in parsed.events] == ["c"]
    assert parsed.problems == Counter({"ical.time_zone_too_large": 2})


def _zone(tzid: str, *observances: str) -> str:
    return f"BEGIN:VTIMEZONE\r\nTZID:{tzid}\r\n" + "".join(observances) + "END:VTIMEZONE\r\n"


def _observance(rule: str = "", start: str = "16011028T030000", kind: str = "STANDARD") -> str:
    line = f"RRULE:{rule}\r\n" if rule else ""
    return (
        f"BEGIN:{kind}\r\nDTSTART:{start}\r\nTZOFFSETFROM:+0200\r\nTZOFFSETTO:+0100\r\n"
        f"{line}END:{kind}\r\n"
    )


_SUMMER = (
    "BEGIN:DAYLIGHT\r\nDTSTART:16010325T020000\r\nTZOFFSETFROM:+0100\r\nTZOFFSETTO:+0200\r\n"
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU\r\nEND:DAYLIGHT\r\n"
)


def _definition(text: str) -> vtimezone.Definition | None:
    tops, _ = lines.read(text.encode())
    return vtimezone.definition(tops[0])


@pytest.mark.parametrize(
    "rule",
    [
        "FREQ=YEARLY;BYMONTH=" + ",".join(map(str, range(1, vtimezone.MAX_RULE_MONTHS + 2))),
        "FREQ=YEARLY;BYMONTH=10;BYDAY=" + ",".join(f"{n}SU" for n in range(1, 5)),
        "FREQ=YEARLY;BYMONTH=10;BYMONTHDAY="
        + ",".join(map(str, range(1, vtimezone.MAX_RULE_MONTHDAYS + 2))),
    ],
)
def test_a_vtimezone_rule_beyond_its_list_caps_is_too_large(rule: str) -> None:
    with pytest.raises(Skip) as refused:
        _definition(_zone("Z", _observance(rule), _SUMMER))
    assert refused.value.code == "ical.time_zone_too_large"
    parsed = _parse(_calendar(_zone("Z", _observance(rule), _SUMMER), _event("u", _IN_Z)))
    assert parsed.problems == Counter({"ical.time_zone_too_large": 1})


_IN_Z = "DTSTART;TZID=Z:20260101T100000"


def test_a_vtimezone_rule_at_its_list_caps_is_compared() -> None:
    days = ",".join(map(str, range(25, 25 + vtimezone.MAX_RULE_MONTHDAYS - 3)))
    rule = f"FREQ=YEARLY;BYMONTH=10;BYDAY=SU;BYMONTHDAY={days}"
    found = _definition(_zone("Z", _observance(rule), _SUMMER))
    assert found is not None
    assert _parse(_calendar(_zone("Z", _observance(rule), _SUMMER), _event("u", _IN_Z))).events


def test_a_vtimezone_beyond_its_observances_is_too_large() -> None:
    fixed = [_observance(start=f"{1700 + n}0101T000000") for n in range(vtimezone.MAX_OBSERVANCES)]
    assert _definition(_zone("Z", *fixed)) is not None
    with pytest.raises(Skip):
        _definition(_zone("Z", *fixed, _observance(start="26000101T000000")))


def test_a_vtimezone_beyond_its_onsets_is_too_large() -> None:
    rdates = ",".join(f"{1700 + n}0101T000000" for n in range(vtimezone.MAX_ONSETS))
    observance = _observance().replace("END:STANDARD", f"RDATE:{rdates}\r\nEND:STANDARD")
    with pytest.raises(Skip):
        _definition(_zone("Z", observance))


def _old_days_of(rule: ParsedRule, year: int, month: int, start_day: int = 1) -> list[int]:
    """The day lists `days_of` built before re-check RC7a-1: the oracle."""
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


@pytest.mark.parametrize("seed", range(4))
def test_days_of_by_arithmetic_picks_the_days_the_lists_picked(seed: int) -> None:
    rng = random.Random(seed)
    weekdays = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
    for _ in range(400):
        parts = ["FREQ=YEARLY", f"BYMONTH={rng.randrange(1, 13)}"]
        if rng.random() < 0.8:
            days = {
                f"{rng.choice(['', '1', '2', '-1', '5', '-5'])}{rng.choice(weekdays)}"
                for _ in range(rng.randrange(1, 4))
            }
            parts.append("BYDAY=" + ",".join(sorted(days)))
        if rng.random() < 0.4:
            first = rng.randrange(-31, 25)
            first = first if first else 1
            parts.append("BYMONTHDAY=" + ",".join(str(first + n) for n in range(7) if first + n))
        try:
            rule = parse_rule(";".join(parts))
        except RuleInvalid:
            continue
        year, month = rng.randrange(1601, 2400), rule.bymonth[0]
        start_day = rng.randrange(1, 32)
        assert vtimezone.days_of(rule, year, month, start_day) == _old_days_of(
            rule, year, month, start_day
        )


def _spent(found: vtimezone.Definition, wall: datetime) -> int:
    spent: list[int] = []
    found.offset_at(wall, spent.append)
    return sum(spent)


def test_one_offset_costs_by_the_ruled_observances_and_their_lists_only() -> None:
    simple = _definition(_zone("Z", _observance("FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU"), _SUMMER))
    longer = _definition(
        _zone("Z", _observance("FREQ=YEARLY;BYMONTH=10,11;BYDAY=-1SU,1SA,2MO"), _SUMMER)
    )
    fixed = [
        _observance(start=f"{1700 + n}0101T000000") for n in range(vtimezone.MAX_OBSERVANCES - 2)
    ]
    many = _definition(
        _zone("Z", *fixed, _observance("FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU"), _SUMMER)
    )
    assert simple is not None and longer is not None and many is not None
    wall = datetime(2026, 7, 1, 12)
    assert _spent(longer, wall) > _spent(simple, wall)
    assert _spent(many, wall) == _spent(simple, wall)  # unruled observances: a bisection
