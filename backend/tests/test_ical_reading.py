"""Reading iCalendar files (plan M10 decision 10, Task 7a): lenient, every refusal
counted by code. The sample files under `tests/data/ical` are written for these tests
in the shapes Google, Outlook, Apple and Nextcloud export."""

from collections import Counter
from datetime import datetime, timedelta

import pytest

from app.modules.calendars.ical import reading
from app.modules.calendars.ical.drafts import (
    AttendeeDraft,
    EventDraft,
    Response,
    Role,
    Status,
    Visibility,
)
from tests.support.ical_occurrences import Span, effective, sample, utc


def _read(name: str, zone: str = "Europe/Berlin") -> tuple[dict[str, EventDraft], Counter[str]]:
    parsed = reading.parse(sample(name), default_zone=zone, limit=5000)
    return {draft.uid: draft for draft in parsed.events}, parsed.problems


def _hour(start: datetime, minutes: int = 60) -> Span:
    return (start, start + timedelta(minutes=minutes))


GOOGLE_SERIES = "3k5b2c1q9t8v7r6p0m4n2l1j0h@google.com"
OUTLOOK_SERIES = (
    "040000008200E00074C5B7101A82E00800000000D0A1B2C3D4E5F6010000000000000000"
    "10000000A1B2C3D4E5F60718293A4B5C6D7E8F"
)
OUTLOOK_TOKYO = (
    "040000008200E00074C5B7101A82E00800000000F0E1D2C3B4A5968701000000000000000"
    "10000000F0E1D2C3B4A59687"
)

REAL_WORLD: dict[str, tuple[dict[str, list[Span]], dict[str, int]]] = {
    "google": (
        {
            # weekly on Mondays 09:30 Berlin; 6 April deleted; 30 March moved to 11:00;
            # UNTIL 20 April 07:29:59 UTC ends just before that day's 09:30 CEST
            GOOGLE_SERIES: [
                _hour(utc(2026, 3, 23, 8, 30), 15),
                _hour(utc(2026, 3, 30, 9, 0), 15),
                _hour(utc(2026, 4, 13, 7, 30), 15),
            ],
            # all-day, three days, floating on 00:00 UTC
            "0a1b2c3d4e5f60718293a4b5c6@google.com": [(utc(2026, 4, 3), utc(2026, 4, 6))],
        },
        {},
    ),
    "outlook": (
        {
            # last Tuesday of the month 14:00 "W. Europe Standard Time", three times
            OUTLOOK_SERIES: [
                _hour(utc(2026, 10, 27, 13)),
                _hour(utc(2026, 11, 24, 13)),
                _hour(utc(2026, 12, 29, 13)),
            ],
            # "Tokyo Standard Time" without a VTIMEZONE in the file
            OUTLOOK_TOKYO: [_hour(utc(2026, 11, 10, 0))],
        },
        {},
    ),
    "apple": (
        {
            # daily 18:30 Berlin across the end of summer time on 25 October
            "6F1C2B9E-3D4A-4E5F-8A7B-1C2D3E4F5A6B": [
                _hour(utc(2026, 10, 24, 16, 30), 90),
                _hour(utc(2026, 10, 25, 17, 30), 90),
                _hour(utc(2026, 10, 26, 17, 30), 90),
            ],
        },
        # Apple's placeholder alarm with an absolute trigger in 1976
        {"ical.alarm_unsupported": 1},
    ),
    "nextcloud": (
        {
            # Mondays and Wednesdays, COUNT=4, the first Wednesday deleted
            "2b3c4d5e-6f70-4812-9a3b-4c5d6e7f8091": [
                _hour(utc(2026, 11, 2, 18), 90),
                _hour(utc(2026, 11, 9, 18), 90),
                _hour(utc(2026, 11, 11, 18), 90),
            ],
        },
        {},
    ),
    "until_date": (
        {
            # UNTIL as a date with a start in New York: that whole day still counts
            "until-date@herd.test": [
                *(_hour(utc(2026, 3, day, 14), 30) for day in (5, 6, 7)),
                *(_hour(utc(2026, 3, day, 13), 30) for day in (8, 9, 10)),
            ],
        },
        {},
    ),
    "until_local": (
        {
            # UNTIL as a local time (no Z): read as the series' wall time, inclusive
            "until-local@herd.test": [
                *(_hour(utc(2026, 3, day, 8)) for day in (27, 28)),
                *(_hour(utc(2026, 3, day, 7)) for day in (29, 30)),
            ],
        },
        {},
    ),
    "exdate_date": (
        {
            # EXDATE as dates for a series with a time: those days' occurrences go
            "exdate-date@herd.test": [_hour(utc(2026, 6, day, 6), 30) for day in (1, 3, 5)],
        },
        {},
    ),
    "exdate_other_zone": (
        {
            # EXDATE in New York (04:00 EDT = 09:00 Berlin) and in UTC (08:00Z)
            "exdate-other-zone@herd.test": [_hour(utc(2026, 3, day, 8)) for day in (9, 12, 13)],
        },
        {},
    ),
    "series_exceptions": (
        {
            "series-exceptions@herd.test": [
                _hour(utc(2026, 10, 26, 14)),
                _hour(utc(2026, 10, 29, 14)),
                _hour(utc(2026, 11, 2, 17), 30),  # moved to London
                _hour(utc(2026, 11, 7, 15)),  # the RDATE
                _hour(utc(2026, 11, 9, 15)),
                _hour(utc(2026, 11, 16, 15)),
                _hour(utc(2026, 11, 19, 15)),
            ],
        },
        {},
    ),
}


@pytest.mark.parametrize("name", sorted(REAL_WORLD))
def test_reading_real_world_files(name: str) -> None:
    expected, problems = REAL_WORLD[name]
    drafts, found = _read(f"{name}.ics")
    assert {uid: effective(draft) for uid, draft in drafts.items()} == expected
    assert found == Counter(problems)


def test_google_keeps_content_people_alarms_and_the_moved_occurrence() -> None:
    drafts, _ = _read("google.ics")
    series = drafts[GOOGLE_SERIES]
    assert series.series.tzid == "Europe/Berlin"
    assert series.series.rrule == "FREQ=WEEKLY;UNTIL=20260420T072959Z;BYDAY=MO"
    content = series.content
    assert (content.title, content.location) == ("Daily Stand-up", "Raum 2")
    assert content.description == "Kurzer Abgleich.\nAgenda im Wiki, Raum siehe Ort."
    assert (content.status, content.visibility, content.busy) == (
        Status.CONFIRMED,
        Visibility.DEFAULT,
        True,
    )
    assert content.sequence == 2
    assert series.organiser == "ada@example.org"
    assert content.attendees == (
        AttendeeDraft("ada@example.org", "Ada Example", Role.REQUIRED, Response.ACCEPTED),
        AttendeeDraft("bert@example.org", "bert@example.org", Role.REQUIRED, Response.NEEDS_ACTION),
    )
    assert series.alarms == (10,)
    (moved,) = series.overrides
    assert moved.recurrence_id == datetime(2026, 3, 30, 9, 30)
    assert moved.series.start == datetime(2026, 3, 30, 11, 0)
    assert moved.content.title == "Daily Stand-up (verschoben)"
    assert moved.content.sequence == 3
    assert moved.content.attendees[1].response is Response.DECLINED
    easter = drafts["0a1b2c3d4e5f60718293a4b5c6@google.com"]
    assert easter.series.all_day and easter.series.tzid is None
    assert easter.content.busy is False


def test_outlook_and_nextcloud_map_class_status_and_roles() -> None:
    outlook, _ = _read("outlook.ics")
    monthly = outlook[OUTLOOK_SERIES]
    assert monthly.series.tzid == "Europe/Berlin"
    assert monthly.content.visibility is Visibility.DEFAULT
    assert monthly.content.description == "Bitte Zahlen mitbringen.\n\n"
    assert monthly.alarms == (15,)
    assert outlook[OUTLOOK_TOKYO].series.tzid == "Asia/Tokyo"
    assert outlook[OUTLOOK_TOKYO].content.visibility is Visibility.PRIVATE
    nextcloud, _ = _read("nextcloud.ics")
    (board,) = nextcloud.values()
    assert board.content.status is Status.TENTATIVE
    assert board.content.visibility is Visibility.PRIVATE  # CONFIDENTIAL
    assert board.organiser == "erika@example.net"
    assert board.content.attendees == (
        AttendeeDraft("clara@example.net", "Clara", Role.OPTIONAL, Response.TENTATIVE),
        AttendeeDraft("dirk@example.net", "Dirk", Role.REQUIRED, Response.DECLINED),
    )


def test_a_cancelled_override_becomes_a_deleted_occurrence() -> None:
    drafts, _ = _read("series_exceptions.ics")
    series = drafts["series-exceptions@herd.test"]
    assert datetime(2026, 11, 12, 10) in series.series.exdates
    assert [o.recurrence_id for o in series.overrides] == [datetime(2026, 11, 2, 10)]
    assert series.series.rdates == (datetime(2026, 11, 7, 10),)
    assert series.alarms == (60,)
    assert series.overrides[0].series.tzid == "Europe/London"
