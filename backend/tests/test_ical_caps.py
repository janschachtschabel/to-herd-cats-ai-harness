"""Structural caps on what one file may make the reader do (re-check M10 Task 7a,
RC7a-1 to RC7a-5): where the work is done inside C calls (`str.join`, sets, sorting)
or grows with a part's size, the part is capped, so a count of Python calls stays a
faithful measure of the work. Each refusal is counted under an `ical.*` code."""

from collections import Counter

from app.modules.calendars.ical import reading, zones


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
