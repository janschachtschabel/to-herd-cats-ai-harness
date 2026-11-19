"""Zone names in iCalendar files (plan M10 decision 10): an IANA name, then the
library's table of Windows names, then the file's VTIMEZONE compared with `tzdata`
(the same offsets from UTC at the events), otherwise the event is skipped with
`ical.time_zone_unknown`. Times without a zone are read in the calendar's zone."""

from collections import Counter
from datetime import datetime

from app.modules.calendars.ical import reading
from tests.support.ical_occurrences import effective, utc

CET_FROM_1601 = """BEGIN:VTIMEZONE
TZID:{tzid}
BEGIN:STANDARD
DTSTART:16011028T030000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:16010325T020000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=3
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
END:DAYLIGHT
END:VTIMEZONE
"""

# The United States' rules since 2007, as Lightning writes them (with its location).
EASTERN_LIGHTNING = """BEGIN:VTIMEZONE
TZID:{tzid}
X-LIC-LOCATION:America/Toronto
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
END:STANDARD
END:VTIMEZONE
"""

ODD_OFFSET = """BEGIN:VTIMEZONE
TZID:Odd Zone
BEGIN:STANDARD
DTSTART:19700101T000000
TZOFFSETFROM:+0123
TZOFFSETTO:+0123
END:STANDARD
END:VTIMEZONE
"""


def _event(uid: str, start: str, extra: str = "") -> str:
    return f"BEGIN:VEVENT\nUID:{uid}\nDTSTAMP:20261118T120000Z\n{start}\nDURATION:PT1H\n{extra}END:VEVENT\n"


def _calendar(*parts: str) -> bytes:
    body = "".join(parts)
    return f"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//t//t//EN\n{body}END:VCALENDAR\n".encode()


def _parse(data: bytes, zone: str = "Europe/Berlin") -> reading.Parsed:
    return reading.parse(data, default_zone=zone, limit=100)


def test_windows_zone_names_and_embedded_vtimezones_resolve() -> None:
    data = _calendar(
        CET_FROM_1601.format(tzid="Customized Time Zone"),
        CET_FROM_1601.format(tzid="(UTC+01:00) Amsterdam, Berlin, Bern, Rom, Stockholm, Wien"),
        EASTERN_LIGHTNING.format(tzid="Eastern (Lightning)"),
        _event("windows", 'DTSTART;TZID="W. Europe Standard Time":20260710T090000'),
        _event("custom", 'DTSTART;TZID="Customized Time Zone":20260710T090000'),
        _event(
            "custom-recurring",
            'DTSTART;TZID="(UTC+01:00) Amsterdam, Berlin, Bern, Rom, Stockholm, Wien":'
            "20260327T090000",
            "RRULE:FREQ=DAILY;COUNT=3\n",
        ),
        _event(
            "global-id", "DTSTART;TZID=/mozilla.org/20050126_1/America/New_York:20260710T090000"
        ),
        _event("lightning", 'DTSTART;TZID="Eastern (Lightning)":20260710T090000'),
        _event("slashes", "DTSTART;TZID=/Asia/Tokyo:20260710T090000"),
    )
    parsed = _parse(data)
    assert parsed.problems == Counter()
    zones = {draft.uid: draft.series.tzid for draft in parsed.events}
    assert zones == {
        "windows": "Europe/Berlin",
        # the VTIMEZONE's offsets match Berlin's (the table's zone for W. Europe)
        "custom": "Europe/Berlin",
        "custom-recurring": "Europe/Berlin",
        "global-id": "America/New_York",
        # X-LIC-LOCATION names a zone with the same offsets: taken first
        "lightning": "America/Toronto",
        "slashes": "Asia/Tokyo",
    }
    recurring = next(d for d in parsed.events if d.uid == "custom-recurring")
    assert [start for start, _ in effective(recurring)] == [
        utc(2026, 3, 27, 8),
        utc(2026, 3, 28, 8),
        utc(2026, 3, 29, 7),  # summer time from 29 March, as in the VTIMEZONE
    ]


def test_a_vtimezone_that_disagrees_with_its_location_is_compared_not_trusted() -> None:
    # X-LIC-LOCATION says Toronto, the offsets say Berlin: the offsets win.
    lying = CET_FROM_1601.format(tzid="Lying").replace(
        "TZID:Lying\n", "TZID:Lying\nX-LIC-LOCATION:America/Toronto\n"
    )
    parsed = _parse(_calendar(lying, _event("lying", "DTSTART;TZID=Lying:20260710T090000")))
    assert [d.series.tzid for d in parsed.events] == ["Europe/Berlin"]


def test_an_unknown_zone_skips_the_event_with_a_code() -> None:
    data = _calendar(
        ODD_OFFSET,
        _event("no-definition", "DTSTART;TZID=Mars/Olympus Mons:20260710T090000"),
        _event("odd-offset", "DTSTART;TZID=Odd Zone:20260710T090000"),
        _event("end-unknown", "DTSTART;TZID=Europe/Berlin:20260710T090000").replace(
            "DURATION:PT1H\n", "DTEND;TZID=Nowhere:20260710T100000\n"
        ),
        _event("fine", "DTSTART;TZID=Europe/Berlin:20260710T090000"),
    )
    parsed = _parse(data)
    assert [d.uid for d in parsed.events] == ["fine"]
    assert parsed.problems == Counter({"ical.time_zone_unknown": 3})


def test_floating_times_use_the_default_zone() -> None:
    data = _calendar(
        _event("floating", "DTSTART:20260710T090000", "RRULE:FREQ=DAILY;COUNT=2\n"),
        _event("utc-once", "DTSTART:20260710T070000Z"),
        _event("utc-recurring", "DTSTART:20260327T080000Z", "RRULE:FREQ=DAILY;COUNT=3\n"),
    )
    parsed = _parse(data, zone="Pacific/Auckland")
    drafts = {d.uid: d for d in parsed.events}
    floating = drafts["floating"].series
    assert (floating.tzid, floating.start) == ("Pacific/Auckland", datetime(2026, 7, 10, 9))
    assert effective(drafts["floating"])[0][0] == utc(2026, 7, 9, 21)
    # A single start in UTC takes the calendar's zone (the instant stays) ...
    once = drafts["utc-once"].series
    assert (once.tzid, once.start) == ("Pacific/Auckland", datetime(2026, 7, 10, 19))
    # ... a series in UTC recurs in UTC (RFC 5545), across Europe's change too.
    recurring = drafts["utc-recurring"]
    assert recurring.series.tzid == "UTC"
    assert [s for s, _ in effective(recurring)] == [utc(2026, 3, d, 8) for d in (27, 28, 29)]


def test_a_zone_must_match_at_the_events_own_times() -> None:
    # Like Berlin, but summer time starts on the last Saturday of March (28 March 2026,
    # a day early): the weekly noon samples of 2026 (Thursdays) cannot tell the two
    # apart, the event's own time on that Saturday can.
    saturday = CET_FROM_1601.format(tzid="Saturday Spring").replace(
        "RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=3", "RRULE:FREQ=YEARLY;BYDAY=-1SA;BYMONTH=3"
    )
    parsed = _parse(
        _calendar(
            saturday,
            _event("on-the-day", "DTSTART;TZID=Saturday Spring:20260328T120000"),
            _event("in-summer", "DTSTART;TZID=Saturday Spring:20260710T090000"),
        )
    )
    assert [(d.uid, d.series.tzid) for d in parsed.events] == [("in-summer", "Europe/Berlin")]
    assert parsed.problems == Counter({"ical.time_zone_unknown": 1})
