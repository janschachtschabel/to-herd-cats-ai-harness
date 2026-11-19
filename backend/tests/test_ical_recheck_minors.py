"""The minor findings of the re-check of M10 Task 7a (RC7a-6 to RC7a-10)."""

from collections import Counter

import pytest

from app.modules.calendars.ical import reading


def _calendar(*parts: str) -> bytes:
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "".join(parts) + "END:VCALENDAR\r\n").encode()


def _event(uid: str, body: str) -> str:
    return f"BEGIN:VEVENT\r\nUID:{uid}\r\n{body}\r\nEND:VEVENT\r\n"


def _parse(data: bytes) -> reading.Parsed:
    return reading.parse(data, default_zone="Europe/Berlin", limit=5000)


@pytest.mark.parametrize("digits", [11, 4_301, 100_000])
def test_an_overlong_sequence_keeps_its_event_capped_and_counted(digits: int) -> None:
    """RC7a-8: beyond Python's digit limit `int()` raised and the event was lost; now
    the largest sequence is taken (a later version stays later) and counted."""
    body = f"DTSTART:20260101T100000Z\r\nSEQUENCE:{'9' * digits}"
    parsed = _parse(_calendar(_event("u", body)))
    assert parsed.events[0].content.sequence == 2**31 - 1
    assert parsed.problems == Counter({"ical.sequence_capped": 1})


def test_a_sequence_within_its_range_is_read_as_written() -> None:
    parsed = _parse(_calendar(_event("u", "DTSTART:20260101T100000Z\r\nSEQUENCE:2147483647")))
    assert parsed.events[0].content.sequence == 2**31 - 1
    assert not parsed.problems
