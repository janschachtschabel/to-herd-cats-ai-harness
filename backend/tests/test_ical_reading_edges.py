"""What reading does with files that bend or break iCalendar (plan M10 decision 10,
Review Focus 4): it takes what it can, never raises for the file's sake, and counts
everything it leaves out by code."""

from collections import Counter
from datetime import datetime, timedelta

import pytest

from app.modules.calendars.ical import problems, reading
from app.modules.calendars.ical.drafts import MAX_ATTENDEES, MAX_DESCRIPTION, MAX_TITLE


def _event(
    uid: str | None, *lines: str, start: str = "DTSTART;TZID=Europe/Berlin:20260710T090000"
) -> str:
    head = f"UID:{uid}\n" if uid is not None else ""
    body = "".join(f"{line}\n" for line in lines)
    return f"BEGIN:VEVENT\n{head}DTSTAMP:20261118T120000Z\n{start}\n{body}END:VEVENT\n"


def _calendar(*parts: str) -> bytes:
    return (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//t//t//EN\n" + "".join(parts) + "END:VCALENDAR\n"
    ).encode()


def _parse(data: bytes, limit: int = 5000) -> reading.Parsed:
    return reading.parse(data, default_zone="Europe/Berlin", limit=limit)


def test_html_in_descriptions_stays_text() -> None:
    html = '<script>alert(1)</script><b>fett</b> &amp; <a href="https://x.test">x</a>'
    parsed = _parse(
        _calendar(
            _event("plain", f"DESCRIPTION:{html}", "SUMMARY:<img src=x onerror=alert(1)>"),
            _event("alt-only", f"X-ALT-DESC;FMTTYPE=text/html:<p>{html}</p>"),
            _event("both", "DESCRIPTION:Text", "X-ALT-DESC;FMTTYPE=text/html:<p>HTML</p>"),
        )
    )
    drafts = {d.uid: d.content for d in parsed.events}
    assert drafts["plain"].description == html
    assert drafts["plain"].title == "<img src=x onerror=alert(1)>"
    assert drafts["alt-only"].description == f"<p>{html}</p>"
    assert drafts["both"].description == "Text"


def test_parse_stops_at_the_limit_and_counts_the_rest() -> None:
    events = [_event(f"e{n}") for n in range(25)]
    # an override of an event within the limit still belongs to it
    events.append(_event("e1", "RECURRENCE-ID;TZID=Europe/Berlin:20260711T090000", "SUMMARY:moved"))
    events[1] = _event("e1", "RRULE:FREQ=DAILY;COUNT=3")
    parsed = _parse(_calendar(*events), limit=10)
    assert [d.uid for d in parsed.events] == [f"e{n}" for n in range(10)]
    assert len(parsed.events[1].overrides) == 1
    assert parsed.problems == Counter({"ical.over_limit": 15})


def test_a_large_file_is_counted_beyond_the_limit() -> None:
    data = _calendar(*(_event(f"many-{n}", "SUMMARY:x") for n in range(20_000)))
    parsed = _parse(data, limit=5000)
    assert len(parsed.events) == 5000
    assert parsed.problems == Counter({"ical.over_limit": 15_000})


@pytest.mark.parametrize("freq", ["SECONDLY", "MINUTELY", "HOURLY"])
def test_rules_below_daily_are_counted_not_read(freq: str) -> None:
    parsed = _parse(_calendar(_event("dense", f"RRULE:FREQ={freq};COUNT=100000"), _event("fine")))
    assert [d.uid for d in parsed.events] == ["fine"]
    assert parsed.problems == Counter({"ical.rrule_unsupported": 1})


@pytest.mark.parametrize(
    ("lines", "code"),
    [
        (("RRULE:FREQ=WEEKLY;BYDAY=1MO",), "ical.rrule_invalid"),
        (("RRULE:FREQ=DAILY;BYHOUR=9",), "ical.rrule_unsupported"),
        (("RRULE:FREQ=DAILY", "RRULE:FREQ=WEEKLY"), "ical.rrule_unsupported"),
        (("EXRULE:FREQ=DAILY",), "ical.rrule_unsupported"),
        (("DTEND;TZID=Europe/Berlin:20260710T080000",), "ical.time_invalid"),
        (("DURATION:soon",), "ical.time_invalid"),
    ],
)
def test_broken_times_and_rules_skip_the_event(lines: tuple[str, ...], code: str) -> None:
    parsed = _parse(_calendar(_event("bad", *lines)))
    assert (parsed.events, parsed.problems) == ([], Counter({code: 1}))


@pytest.mark.parametrize(
    "start",
    ["DTSTART:2026-07-10", "DTSTART;TZID=Europe/Berlin:2026071OT090000", "DTSTART:٢٠٢٦0710", ""],
)
def test_an_unreadable_or_missing_start_skips_the_event(start: str) -> None:
    parsed = _parse(_calendar(_event("bad", start=start)))
    assert (parsed.events, parsed.problems) == ([], Counter({"ical.time_invalid": 1}))


def test_years_outside_the_calendar_are_refused_or_cut() -> None:
    parsed = _parse(
        _calendar(
            _event("old", "RRULE:FREQ=YEARLY", start="DTSTART;VALUE=DATE:18500101"),
            _event("far-until", "RRULE:FREQ=YEARLY;UNTIL=99991231T235959Z"),
            _event(
                "far-until-date",
                "RRULE:FREQ=YEARLY;UNTIL=99991231",  # its end of day lies past datetime's
                start="DTSTART;TZID=America/New_York:20260710T090000",
            ),
            _event("early-until", "RRULE:FREQ=YEARLY;UNTIL=18000101T000000Z"),
        )
    )
    assert parsed.problems == Counter({"ical.time_out_of_range": 1})
    rules = {d.uid: d.series.rrule for d in parsed.events}
    # an UNTIL beyond 2399 ends nothing earlier; one before 1900 ends at the start
    assert rules == {
        "far-until": "FREQ=YEARLY",
        "far-until-date": "FREQ=YEARLY",
        "early-until": "FREQ=YEARLY;UNTIL=19000101T000000Z",
    }


def test_a_rule_that_never_matches_is_read_as_its_start_alone() -> None:
    # every twelfth month from February: always February, never a 30th
    dead_rule = "RRULE:FREQ=MONTHLY;INTERVAL=12;BYMONTHDAY=30"
    parsed = _parse(
        _calendar(_event("dead", dead_rule, start="DTSTART;TZID=Europe/Berlin:20260210T090000"))
    )
    (dead,) = parsed.events
    assert dead.series.rrule is None
    assert parsed.problems == Counter({"ical.rrule_never_matches": 1})


def test_uids_must_be_there_once_and_not_too_long() -> None:
    parsed = _parse(
        _calendar(
            _event(None),
            _event("x" * 501),
            _event("twice", "SUMMARY:first"),
            _event("twice", "SUMMARY:second"),
        )
    )
    assert [(d.uid, d.content.title) for d in parsed.events] == [("twice", "first")]
    assert parsed.problems == Counter({"ical.uid_missing": 2, "ical.duplicate_uid": 1})


def test_overrides_that_match_nothing_are_counted() -> None:
    parsed = _parse(
        _calendar(
            _event("series", "RRULE:FREQ=DAILY;COUNT=3"),
            _event("series", "RECURRENCE-ID;TZID=Europe/Berlin:20260711T100000"),  # no such time
            _event(
                "series", "RECURRENCE-ID;RANGE=THISANDFUTURE;TZID=Europe/Berlin:20260711T090000"
            ),
            _event("orphan", "RECURRENCE-ID;TZID=Europe/Berlin:20260711T090000"),
            _event("orphan", "RECURRENCE-ID;TZID=Europe/Berlin:20260712T090000"),
        )
    )
    assert [(d.uid, d.overrides) for d in parsed.events] == [("series", ())]
    # an override whose series is not in the file (one occurrence a person is invited
    # to, RFC 4791 4.1) has a code of its own, once per override (R7a-14)
    assert parsed.problems == Counter(
        {"ical.override_unmatched": 1, "ical.override_unsupported": 1, "ical.override_orphaned": 2}
    )


def test_an_override_wins_over_an_exdate_for_the_same_occurrence() -> None:
    parsed = _parse(
        _calendar(
            _event("s", "RRULE:FREQ=DAILY;COUNT=3", "EXDATE;TZID=Europe/Berlin:20260711T090000"),
            _event("s", "RECURRENCE-ID;TZID=Europe/Berlin:20260711T090000", "SUMMARY:moved"),
        )
    )
    (series,) = parsed.events
    assert series.series.exdates == ()
    assert [o.recurrence_id for o in series.overrides] == [datetime(2026, 7, 11, 9)]


def test_texts_are_cut_cleaned_and_counted() -> None:
    parsed = _parse(
        _calendar(
            _event(
                "long",
                f"SUMMARY:{'t' * (MAX_TITLE + 5)}",
                f"DESCRIPTION:{'d' * (MAX_DESCRIPTION + 1)}",
                "LOCATION:Raum\x00 1\x07",
            )
        )
    )
    (long,) = parsed.events
    assert len(long.content.title) == MAX_TITLE
    assert len(long.content.description) == MAX_DESCRIPTION
    assert long.content.location == "Raum 1"  # control characters never reach Postgres
    assert parsed.problems == Counter({"ical.text_cut": 1})


def test_attendees_beyond_the_limit_or_without_an_address_are_dropped() -> None:
    people = [f"ATTENDEE:mailto:p{n}@example.org" for n in range(MAX_ATTENDEES + 3)]
    parsed = _parse(
        _calendar(
            _event("many", *people),
            _event("odd", "ATTENDEE;CN=Room:urn:uuid:1234", "ATTENDEE:MAILTO:Ok@Example.org"),
        )
    )
    drafts = {d.uid: d for d in parsed.events}
    assert len(drafts["many"].content.attendees) == MAX_ATTENDEES
    assert [a.email for a in drafts["odd"].content.attendees] == ["Ok@Example.org"]
    assert parsed.problems == Counter({"ical.attendee_dropped": 2})


def test_alarms_become_minutes_before_the_start() -> None:
    alarms = [
        "TRIGGER:-PT15M",
        "TRIGGER:-P1D",
        "TRIGGER;RELATED=END:-PT30M",  # an hour's event: 30 minutes after the start
        "TRIGGER:PT5M",
        "TRIGGER:-PT15M",  # the same again: one reminder
        "TRIGGER:-P5W",  # beyond four weeks
        "TRIGGER:-PT0M",
    ]
    blocks = [f"BEGIN:VALARM\nACTION:DISPLAY\nDESCRIPTION:x\n{a}\nEND:VALARM" for a in alarms]
    parsed = _parse(_calendar(_event("alarms", "DURATION:PT1H", *blocks)))
    (event,) = parsed.events
    assert event.alarms == (0, 15, 1440)  # at most three, earliest first
    assert parsed.problems == Counter({"ical.alarm_unsupported": 1})


def test_the_default_busy_follows_the_kind_of_event() -> None:
    parsed = _parse(
        _calendar(
            _event("timed"),
            _event("all-day", start="DTSTART;VALUE=DATE:20260710"),
            _event("all-day-opaque", "TRANSP:OPAQUE", start="DTSTART;VALUE=DATE:20260710"),
            _event("odd-class", "CLASS:X-SECRET"),
        )
    )
    drafts = {d.uid: d for d in parsed.events}
    assert [drafts[u].content.busy for u in ("timed", "all-day", "all-day-opaque")] == [
        True,
        False,
        True,
    ]
    assert drafts["all-day"].series.duration == timedelta(days=1)
    assert drafts["odd-class"].content.visibility.value == "private"  # RFC 5545: unknown is private


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x00\xff\xfe garbage",
        b"<html><body>not a calendar</body></html>",
        b"BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:cut\nDTSTART:20260710T090000Z\n",
        b"END:VEVENT\nEND:VCALENDAR\n",
    ],
)
def test_unreadable_data_is_counted_never_raised(data: bytes) -> None:
    parsed = _parse(data)
    assert parsed.events == []
    assert parsed.problems == Counter({"ical.unreadable": 1})


def test_broken_lines_and_other_components_are_counted() -> None:
    data = _calendar(
        _event("ok", "THIS LINE HAS NO COLON", "SUMMARY:fine"),
        "BEGIN:VTODO\nUID:todo\nEND:VTODO\n",
        "BEGIN:VJOURNAL\nUID:journal\nEND:VJOURNAL\n",
    )
    parsed = _parse(b"\xef\xbb\xbf" + data)  # with a byte order mark
    assert [d.content.title for d in parsed.events] == ["fine"]
    assert parsed.problems == Counter({"ical.line_unreadable": 1, "ical.not_an_event": 2})


def test_every_code_is_listed() -> None:
    assert problems.CODES >= {
        "ical.unreadable",
        "ical.time_zone_unknown",
        "ical.rrule_unsupported",
        "ical.over_limit",
    }
    assert all(code.startswith("ical.") for code in problems.CODES)


@pytest.mark.parametrize(
    ("written", "hours"),
    [
        ("PT36H", 36),  # exact hours, also across the end of summer time
        ("P1DT12H", 37),  # a day is nominal: the same wall time a day later, then 12 h
        ("P1W", 7 * 24 + 1),
    ],
)
def test_a_duration_counts_days_by_the_wall_clock_and_hours_exactly(
    written: str, hours: int
) -> None:
    start = "DTSTART;TZID=Europe/Berlin:20261024T120000"
    parsed = _parse(_calendar(_event("d", f"DURATION:{written}", start=start)))
    (event,) = parsed.events
    assert event.series.duration == timedelta(hours=hours)
