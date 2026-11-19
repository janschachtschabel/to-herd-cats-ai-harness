"""Reading never raises for the file's sake (review M10 Task 7a, R7a-3): times at the
ends of `datetime`, VTIMEZONE rules that run past them, and a last guard per event."""

from collections import Counter
from datetime import datetime, timedelta

import pytest

from app.modules.calendars.ical import content, lines, reading
from app.modules.calendars.ical.vtimezone import definition


def _parse(data: bytes) -> reading.Parsed:
    return reading.parse(data, default_zone="Europe/Berlin", limit=5000)


def _calendar(*parts: str) -> bytes:
    return ("BEGIN:VCALENDAR\r\n" + "".join(parts) + "END:VCALENDAR\r\n").encode()


def _event(uid: str, body: str) -> str:
    return f"BEGIN:VEVENT\r\nUID:{uid}\r\n{body}\r\nEND:VEVENT\r\n"


@pytest.mark.parametrize(
    "rule",
    [
        "FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU;COUNT=5000;INTERVAL=3",
        "FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU;UNTIL=23991231T235959Z",
        "FREQ=YEARLY;BYMONTH=12;BYMONTHDAY=31",
    ],
)
@pytest.mark.parametrize("start", ["00010101T000000", "99991231T230000", "16011028T030000"])
def test_a_vtimezone_answers_at_any_wall_time_without_raising(rule: str, start: str) -> None:
    text = (
        "BEGIN:VTIMEZONE\r\nTZID:Edge\r\nBEGIN:STANDARD\r\n"
        f"DTSTART:{start}\r\nTZOFFSETFROM:+1400\r\nTZOFFSETTO:-1200\r\nRRULE:{rule}\r\n"
        "END:STANDARD\r\nEND:VTIMEZONE\r\n"
    )
    tops, _ = lines.read(text.encode())
    found = definition(tops[0])
    assert found is not None
    for wall in (
        datetime(1, 1, 1),
        datetime(1, 1, 2),
        datetime(2026, 6, 1),
        datetime(9999, 12, 31, 23),
    ):
        assert found.offset_at(wall) in (timedelta(hours=14), timedelta(hours=-12))


def test_a_duration_beyond_datetime_is_out_of_range() -> None:
    parsed = _parse(
        _calendar(_event("u1", "DTSTART;TZID=Europe/Berlin:20260101T100000\r\nDURATION:P999999W"))
    )
    assert parsed.problems == Counter({"ical.time_out_of_range": 1})


def test_an_event_the_reader_fails_on_is_counted_and_the_rest_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = content.read

    def failing(part: lines.Component, **kwargs: object) -> object:
        if part.first("SUMMARY") is not None:
            raise ArithmeticError("a defect nobody has found yet")
        return real(part, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(content, "read", failing)
    parsed = _parse(
        _calendar(
            _event("bad", "DTSTART:20260101T100000Z\r\nSUMMARY:x"),
            _event("good", "DTSTART:20260102T100000Z"),
        )
    )
    assert [d.uid for d in parsed.events] == ["good"]
    assert parsed.problems == Counter({"ical.event_unreadable": 1})


def test_a_file_the_line_reader_fails_on_is_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(data: bytes) -> object:
        raise RecursionError

    monkeypatch.setattr(lines, "read", failing)
    parsed = _parse(_calendar(_event("u1", "DTSTART:20260101T100000Z")))
    assert parsed == reading.Parsed([], Counter({"ical.unreadable": 1}))
