"""The minor findings of the re-check of M10 Task 7a (RC7a-6 to RC7a-10)."""

from collections import Counter
from datetime import datetime, timedelta

import pytest

from app.modules.calendars.ical import opaque, reading, writing, zone_names
from app.modules.calendars.ical.drafts import (
    AttendeeDraft,
    Content,
    EventDraft,
    ExportEvent,
    ExportOverride,
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


_KEY = opaque.key_from_secret("an installation's secret key, 32+ characters")


def test_an_empty_secret_gives_no_key() -> None:
    """RC7a-9 (a): an unset `HERD_SECRET_KEY` passed as "" would give a key anyone can
    compute."""
    with pytest.raises(ValueError, match="secret"):
        opaque.key_from_secret("")


def test_the_opaque_uid_names_its_purpose_and_audience_apart() -> None:
    """RC7a-9 (b): a feed's id and a person's id never share a name space, and no
    audience and UID run into each other (length-prefixed parts)."""
    feed = opaque.opaque_uid("u", key=_KEY, purpose=opaque.Purpose.FEED, audience="1")
    export = opaque.opaque_uid("u", key=_KEY, purpose=opaque.Purpose.EXPORT, audience="1")
    assert feed != export
    joined = opaque.opaque_uid("b\x00c", key=_KEY, purpose=opaque.Purpose.FEED, audience="a")
    other = opaque.opaque_uid("c", key=_KEY, purpose=opaque.Purpose.FEED, audience="a\x00b")
    assert joined != other


def test_an_override_is_written_with_its_own_stamp() -> None:
    """RC7a-9 (c): a visible override's DTSTAMP is its own row's last change."""
    moved = Series(datetime(2026, 7, 2, 11), timedelta(hours=1), "Europe/Berlin", False)
    series = Series(
        datetime(2026, 7, 1, 9), timedelta(hours=1), "Europe/Berlin", False, "FREQ=DAILY"
    )
    override = ExportOverride(
        datetime(2026, 7, 2, 9), moved, Content(title="moved"), stamp=utc(2026, 11, 18, 7)
    )
    event = ExportEvent(
        uid="u", series=series, content=Content(), stamp=utc(2026, 11, 1), overrides=(override,)
    )
    data = writing.event_ics(event, now=utc(2026, 11, 19))
    stamps = [line for line in data.decode().split("\r\n") if line.startswith("DTSTAMP")]
    assert stamps == ["DTSTAMP:20261101T000000Z", "DTSTAMP:20261118T070000Z"]


def _fixed(tzid: str, offset: str, location: str = "") -> str:
    hint = f"X-LIC-LOCATION:{location}\r\n" if location else ""
    return (
        f"BEGIN:VTIMEZONE\r\nTZID:{tzid}\r\n{hint}BEGIN:STANDARD\r\nDTSTART:19700101T000000\r\n"
        f"TZOFFSETFROM:{offset}\r\nTZOFFSETTO:{offset}\r\nEND:STANDARD\r\nEND:VTIMEZONE\r\n"
    )


def _zone_of(tzid: str, offset: str, location: str = "") -> str | None:
    body = f'DTSTART;TZID="{tzid}":20260710T090000'
    parsed = _parse(_calendar(_fixed(tzid, offset, location), _event("u", body)))
    return parsed.events[0].series.tzid if parsed.events else None


@pytest.mark.parametrize("hours", [*range(-11, 0), *range(1, 15)])
def test_a_fixed_offset_means_a_canonical_zone_never_etc_or_a_link(hours: int) -> None:
    """RC7a-10: of the zones that fit a definition without changes, a canonical IANA
    zone is chosen; `Etc/…` and links kept for old names (`backward`) only if none
    fits."""
    offset = f"{'+' if hours > 0 else '-'}{abs(hours):02d}00"
    found = _zone_of("Customized Time Zone", offset)
    if found is None:
        pytest.skip(f"no zone has {offset} in 2026")
    assert not found.startswith("Etc/")
    assert found not in zone_names.links()


def test_a_city_or_location_that_names_a_link_means_its_canonical_zone() -> None:
    assert _zone_of("(UTC+08:00) Beijing, Chongqing, Hong Kong", "+0800") == "Asia/Shanghai"
    assert _zone_of("India", "+0530", location="Asia/Calcutta") == "Asia/Kolkata"
    assert _zone_of("Tasmania", "+1000") != "Australia/Tasmania"


def test_the_links_are_read_from_tzdata() -> None:
    links = zone_names.links()
    assert links["Asia/Calcutta"] == "Asia/Kolkata"
    assert links["US/Eastern"] == "America/New_York"
    assert "Europe/Berlin" not in links
