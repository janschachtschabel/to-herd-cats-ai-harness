"""Bytes and components (review M10 Task 7a, R7a-2, R7a-7, R7a-8, R7a-15): what a file's
structure and character set do to reading. Nothing is left out without a code."""

from collections import Counter

from app.modules.calendars.ical import lines, reading


def _event(uid: str, day: int = 1) -> str:
    return f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART:202601{day:02d}T100000Z\r\nEND:VEVENT\r\n"


def _parse(data: bytes) -> reading.Parsed:
    return reading.parse(data, default_zone="Europe/Berlin", limit=5000)


def test_an_event_that_never_ends_does_not_take_the_next_ones_with_it() -> None:
    """R7a-8 (c): one missing `END:VEVENT` used to nest every later event in the open
    one; they were lost with it. A `BEGIN:VEVENT` closes an open VEVENT."""
    unended = "BEGIN:VEVENT\r\nUID:open\r\nDTSTART:20260101T100000Z\r\n"
    data = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        + unended
        + _event("second", 2)
        + _event("third", 3)
        + "END:VCALENDAR\r\n"
    ).encode()
    parsed = _parse(data)
    assert [d.uid for d in parsed.events] == ["open", "second", "third"]
    assert parsed.problems == Counter({"ical.unreadable": 1})


def test_components_nested_beyond_any_calendar_are_counted_and_dropped() -> None:
    """A calendar needs three levels (VCALENDAR, VEVENT, VALARM); deeper nesting is
    dropped as `ical.unreadable`, the event around it is read."""
    deep = "BEGIN:X-DEEP\r\n" * 50 + "END:X-DEEP\r\n" * 50
    data = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:u1\r\nDTSTART:20260101T100000Z\r\n"
        + deep
        + "END:VEVENT\r\n"
        + _event("u2", 2)
        + "END:VCALENDAR\r\n"
    ).encode()
    parsed = _parse(data)
    assert [d.uid for d in parsed.events] == ["u1", "u2"]
    assert parsed.problems == Counter({"ical.unreadable": 1})


def test_lines_read_stays_flat() -> None:
    tops, found = lines.read(
        ("BEGIN:VCALENDAR\r\n" + "BEGIN:X\r\n" * 10_000 + "END:X\r\n" * 10_000).encode()
    )
    assert found == Counter({"ical.unreadable": 1})
    depth, level = 0, tops
    while level:
        depth += 1
        level = level[0].children
    assert depth <= lines.MAX_DEPTH


def test_a_utf16_file_with_its_byte_order_mark_is_read() -> None:
    text = (
        "BEGIN:VCALENDAR\r\n"
        + _event("u1").replace("UID:u1", "UID:u1\r\nSUMMARY:Grüße")
        + "END:VCALENDAR\r\n"
    )
    for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
        data = text.encode(encoding)
        if encoding != "utf-16":
            data = ("﻿" + text).encode(encoding)
        parsed = _parse(data)
        assert [d.content.title for d in parsed.events] == ["Grüße"], encoding
        assert parsed.problems == Counter()


def test_text_in_another_character_set_is_counted() -> None:
    """R7a-15: a Latin-1 file is no UTF-8; its broken characters are replaced, and the
    result says so."""
    text = (
        "BEGIN:VCALENDAR\r\n"
        + _event("u1").replace("UID:u1", "UID:u1\r\nSUMMARY:Grüße")
        + "END:VCALENDAR\r\n"
    )
    parsed = _parse(text.encode("latin-1"))
    assert [d.content.title for d in parsed.events] == ["Gr��e"]
    assert parsed.problems == Counter({"ical.text_replaced": 1})


def test_a_component_after_the_calendar_that_is_no_event_is_counted() -> None:
    data = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"
        "BEGIN:VTODO\r\nUID:t\r\nEND:VTODO\r\n" + _event("after")
    ).encode()
    parsed = _parse(data)
    assert [d.uid for d in parsed.events] == ["after"]
    assert parsed.problems == Counter({"ical.not_an_event": 1})
