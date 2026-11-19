"""The minor findings of the re-check of M10 Task 7a (RC7a-6 to RC7a-10)."""

from collections import Counter
from datetime import datetime, timedelta

import pytest

from app.modules.calendars.ical import reading, writing
from app.modules.calendars.ical.drafts import (
    AttendeeDraft,
    Content,
    EventDraft,
    ExportEvent,
    Response,
)
from app.modules.calendars.recurrence import Series
from tests.support.ical_occurrences import utc

_SERIES = Series(datetime(2026, 7, 1, 9), timedelta(hours=1), "Europe/Berlin", False)


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


_NAMES = [
    "a\\:b",
    "end\\",
    "x\\\\y",
    "Doe\\, John",
    'back\\slash, "quoted" ^caret; semi',
    "\\",
]


@pytest.mark.parametrize("name", _NAMES)
def test_a_backslash_in_an_attendees_name_round_trips_with_the_response(name: str) -> None:
    """RC7a-7: a parameter value is quoted (RFC 5545 3.2) where it holds a backslash and
    read verbatim inside quotes; `^` and `"` go by RFC 6868."""
    attendee = AttendeeDraft("x@y.org", name, response=Response.ACCEPTED)
    draft = EventDraft(uid="u", series=_SERIES, content=Content(attendees=(attendee,)))
    data = writing.event_ics(ExportEvent.of(draft, stamp=utc(2026, 11, 19)), now=utc(2026, 11, 19))
    (back,) = _parse(data).events
    assert back.content.attendees == (attendee,)


@pytest.mark.parametrize(
    ("written", "name"),
    [
        ('CN="a\\b"', "a\\b"),  # quoted: verbatim
        ('CN="Doe, John"', "Doe, John"),
        ("CN=Doe\\, John", "Doe, John"),  # unquoted escapes some producers write
        ("CN=a^'b^^c", 'a"b^c'),  # RFC 6868
        ('CN="end\\"', "end\\"),
    ],
)
def test_a_parameter_is_read_verbatim_inside_quotes(written: str, name: str) -> None:
    body = f"DTSTART:20260101T100000Z\r\nATTENDEE;{written};PARTSTAT=ACCEPTED:mailto:x@y.org"
    (event,) = _parse(_calendar(_event("u", body))).events
    assert event.content.attendees == (AttendeeDraft("x@y.org", name, response=Response.ACCEPTED),)
