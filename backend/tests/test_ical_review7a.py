"""Review of M10 Task 7a (`.superpowers/sdd/m10/review-task-7a.md`): what a hostile or
merely odd file does to `ical.reading.parse`, and what a redacted event gives away.

No test measures the clock (plan M10, Global Constraints): work is counted as Python
calls (`_calls`), and compared between two sizes of the same file.
"""

import hashlib
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import FrameType

import pytest

from app.modules.calendars.ical import opaque, reading, writing
from app.modules.calendars.ical.drafts import Content, ExportEvent
from app.modules.calendars.recurrence import Series
from tests.support.ical_occurrences import effective, utc

BERLIN = "Europe/Berlin"

# Europe's rules under a name no table knows (as Outlook's "Customized Time Zone").
CUSTOM_ZONE = (
    "BEGIN:VTIMEZONE\r\nTZID:Custom\r\n"
    "BEGIN:STANDARD\r\nDTSTART:16011028T030000\r\nTZOFFSETFROM:+0200\r\nTZOFFSETTO:+0100\r\n"
    "{standard_rule}\r\nEND:STANDARD\r\n"
    "BEGIN:DAYLIGHT\r\nDTSTART:16010325T020000\r\nTZOFFSETFROM:+0100\r\nTZOFFSETTO:+0200\r\n"
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU\r\nEND:DAYLIGHT\r\n"
    "END:VTIMEZONE\r\n"
)
EUROPE = "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU"


def _calendar(*parts: str) -> bytes:
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "".join(parts) + "END:VCALENDAR\r\n").encode()


def _event(body: str, uid: str = "u1") -> str:
    return f"BEGIN:VEVENT\r\nUID:{uid}\r\n{body}\r\nEND:VEVENT\r\n"


def _parse(data: bytes) -> reading.Parsed:
    return reading.parse(data, default_zone=BERLIN, limit=5000)


def _calls(work: Callable[[], object]) -> int:
    """How many Python calls (generator resumptions included) `work` makes."""
    count = 0

    def note(frame: FrameType, event: str, arg: object) -> None:
        nonlocal count
        if event == "call":
            count += 1

    work()  # fill the caches (zone names, zone files) first
    sys.setprofile(note)
    try:
        work()
    finally:
        sys.setprofile(None)
    return count


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%S")


# --- R7a-1: zone resolution is quadratic in the times an event writes -----------------


def _exdates_in_a_custom_zone(count: int) -> bytes:
    first = datetime(2026, 6, 1, 10)
    removed = ",".join(_stamp(first + timedelta(days=day)) for day in range(1, count + 1))
    body = (
        f"DTSTART;TZID=Custom:{_stamp(first)}\r\nRRULE:FREQ=DAILY\r\nEXDATE;TZID=Custom:{removed}"
    )
    return _calendar(CUSTOM_ZONE.format(standard_rule=EUROPE), _event(body))


def test_resolving_a_files_own_zone_costs_no_more_per_time_the_more_times_there_are() -> None:
    """One event with EXDATEs in a zone only the file defines: every value resolves the
    zone again, against every time of the event. 4,000 EXDATEs (64 KB) took 286 s
    here; 2,000 took 71 s; a file of 5 MiB would take days."""
    assert len(_parse(_exdates_in_a_custom_zone(50)).events[0].series.exdates) == 50
    small = _calls(lambda: _parse(_exdates_in_a_custom_zone(50)))
    large = _calls(lambda: _parse(_exdates_in_a_custom_zone(100)))
    assert large < 3 * small, (small, large)  # twice the times, about twice the work


# --- R7a-2: an END without its BEGIN scans every open component ----------------------


def _open_components_and_stray_ends(count: int) -> bytes:
    return ("BEGIN:VCALENDAR\r\n" + "BEGIN:A\r\n" * count + "END:B\r\n" * count).encode()


def test_stray_ends_cost_no_more_each_the_more_components_are_open() -> None:
    """`BEGIN:A` n times, then `END:B` n times: each END looks at every open component.
    16,000 of each (256 KB) took 6 s here, so 5 MiB take about 40 minutes."""
    assert _parse(_open_components_and_stray_ends(10)).events == []
    small = _calls(lambda: _parse(_open_components_and_stray_ends(200)))
    large = _calls(lambda: _parse(_open_components_and_stray_ends(400)))
    assert large < 3 * small, (small, large)


# --- R7a-3: three files that make `parse` raise ---------------------------------------

RAISING = {
    # times.py: `begin.wall + timedelta(days=…)` leaves datetime's years (OverflowError)
    "duration_beyond_datetime": _calendar(_event("DTSTART:20260101T100000\r\nDURATION:P999999W")),
    # vtimezone.py: the year of a counted rule's last onset is no year of `date`
    # (ValueError out of `Definition.offset_at`, which nothing catches)
    "vtimezone_rule_beyond_datetime": _calendar(
        CUSTOM_ZONE.format(standard_rule=EUROPE + ";COUNT=5000;INTERVAL=3"),
        _event("DTSTART;TZID=Custom:20260601T100000\r\nDTEND;TZID=Custom:20260601T110000"),
    ),
    # reading.py: `_broken` walks an event's components by recursion (RecursionError)
    "components_nested_deeply_in_an_event": _calendar(
        "BEGIN:VEVENT\r\nUID:u1\r\nDTSTART:20260101T100000Z\r\n"
        + "BEGIN:VALARM\r\n" * 3000
        + "END:VALARM\r\n" * 3000
        + "END:VEVENT\r\n"
    ),
}


@pytest.mark.parametrize("name", sorted(RAISING))
def test_reading_never_raises_for_the_files_sake(name: str) -> None:
    parsed = _parse(RAISING[name])  # must not raise
    assert len(parsed.events) + sum(parsed.problems.values()) >= 1  # read, or counted


# --- R7a-4: every override expands its series again ----------------------------------


def _overrides_at_the_end_of_a_counted_series(count: int) -> bytes:
    first = datetime(2026, 1, 1, 10)
    last = _stamp(first + timedelta(days=1999))
    override = _event(f"DTSTART:{last}Z\r\nRECURRENCE-ID:{last}Z\r\nSUMMARY:again")
    series = _event(f"DTSTART:{_stamp(first)}Z\r\nRRULE:FREQ=DAILY;COUNT=2000")
    return _calendar(series, override * count)


def test_the_overrides_of_one_series_do_not_each_expand_it_from_its_start() -> None:
    """Each override asks `recurrence.is_occurrence`, which expands a counted series
    from its start (7 ms for COUNT=5000). The limit counts events, not overrides:
    2,000 overrides (184 KB) took 14 s here, so 5 MiB take about 6 minutes."""
    one = _calls(lambda: _parse(_overrides_at_the_end_of_a_counted_series(1)))
    forty = _calls(lambda: _parse(_overrides_at_the_end_of_a_counted_series(40)))
    assert forty < 5 * one, (one, forty)


# --- R7a-5: a redacted event's UID can be guessed ------------------------------------


def test_a_redacted_uid_cannot_be_found_by_guessing_the_uid() -> None:
    """The redacted UID is the plain SHA-256 of the event's UID. Whoever sees only
    "busy" can try UIDs a producer numbers (a meeting platform, a booking system, a
    clinic's portal) and learn which event the private one is."""
    series = Series(
        start=datetime(2026, 6, 1, 10), duration=timedelta(hours=1), tzid=BERLIN, all_day=False
    )
    secret = "event_305123456@meetup.example"
    event = ExportEvent(
        uid=secret, series=series, content=Content(title="Selbsthilfegruppe"), stamp=utc(2026, 1, 1)
    )
    written = writing.event_ics(_redacted(event), now=utc(2026, 11, 19))
    guesses = [f"event_{number}@meetup.example" for number in range(305123000, 305124000)]
    found = [
        guess
        for guess in guesses
        if hashlib.sha256(guess.encode()).hexdigest()[:32].encode() in written
    ]
    assert found == []  # with nothing but the feed, no guess can be confirmed


def _redacted(event: ExportEvent) -> ExportEvent:
    # fix wave (R7a-5): the caller names the opaque UID, a keyed hash of the real one
    key = opaque.key_from_secret("an installation's secret key, 32+ characters")
    return ExportEvent(
        uid=event.uid,
        series=event.series,
        content=event.content,
        stamp=event.stamp,
        redacted=True,
        opaque_uid=opaque.opaque_uid(event.uid, key=key, audience="feed-1"),
    )


# --- R7a-6: an occurrence in a gap, named by its instant -----------------------------

# Daily at 02:30 in Berlin; on 29 March 2026 02:30 does not exist: the occurrence
# starts at 03:30 (01:30 UTC) and its RECURRENCE-ID is the wall time 02:30 (Task 2).
GAP_SERIES = (
    "DTSTART;TZID=Europe/Berlin:20260327T023000\r\nDURATION:PT1H\r\nRRULE:FREQ=DAILY;COUNT=5"
)


def test_an_exdate_in_utc_removes_the_occurrence_in_a_gap() -> None:
    parsed = _parse(_calendar(_event(GAP_SERIES + "\r\nEXDATE:20260329T013000Z")))
    starts = [start for start, _ in effective(parsed.events[0])]
    assert datetime(2026, 3, 29, 1, 30, tzinfo=UTC) not in starts
    assert len(starts) == 4


def test_an_override_in_utc_replaces_the_occurrence_in_a_gap() -> None:
    moved = "RECURRENCE-ID:20260329T013000Z\r\nDTSTART:20260329T150000Z\r\nSUMMARY:moved"
    parsed = _parse(_calendar(_event(GAP_SERIES), _event(moved)))
    assert dict(parsed.problems) == {}
    assert [o.recurrence_id for o in parsed.events[0].overrides] == [datetime(2026, 3, 29, 2, 30)]


# --- R7a-7: a line folded inside a character (RFC 5545 3.1) --------------------------


def test_a_line_folded_inside_a_character_is_read_whole() -> None:
    """RFC 5545 3.1: a producer may fold between the octets of one character, so a
    reader unfolds before it decodes."""
    first, second = "ü".encode()
    data = (
        b"BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:u1\r\nDTSTART:20260101T100000Z\r\nSUMMARY:Gr"
        + bytes([first])
        + b"\r\n "
        + bytes([second])
        + "ße\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n".encode()
    )
    assert _parse(data).events[0].content.title == "Grüße"


# --- R7a-8: events left out without a count ------------------------------------------


def test_an_event_after_the_calendars_end_is_read_or_counted() -> None:
    data = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"
        + _event("DTSTART:20260101T100000Z").encode()
    )
    parsed = _parse(data)
    assert len(parsed.events) + sum(parsed.problems.values()) >= 1


def test_an_event_inside_an_event_is_read_or_counted() -> None:
    inner = _event("DTSTART:20260102T100000Z", uid="inner")
    outer = "BEGIN:VEVENT\r\nUID:outer\r\nDTSTART:20260101T100000Z\r\n" + inner + "END:VEVENT\r\n"
    parsed = _parse(_calendar(outer))
    assert len(parsed.events) + sum(parsed.problems.values()) >= 2
