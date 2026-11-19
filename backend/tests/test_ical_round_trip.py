"""Writing iCalendar (plan M10 decision 10, Task 7a): strict, in the RFC's form, and a
written file reads back to the same occurrences."""

from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.calendars.ical import reading, writing
from app.modules.calendars.ical.drafts import (
    AttendeeDraft,
    Content,
    EventDraft,
    ExportEvent,
    OverrideDraft,
    Response,
    Role,
    Status,
    Visibility,
)
from app.modules.calendars.recurrence import Series
from tests.support.ical_occurrences import effective, sample

STAMP = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
SAMPLES = [
    "google.ics",
    "outlook.ics",
    "apple.ics",
    "nextcloud.ics",
    "until_date.ics",
    "until_local.ics",
    "exdate_date.ics",
    "exdate_other_zone.ics",
    "series_exceptions.ics",
]


def _export(draft: EventDraft, **changes: object) -> ExportEvent:
    return replace(ExportEvent.of(draft, stamp=STAMP), **changes)  # type: ignore[arg-type]


def _read_back(data: bytes, zone: str = "Europe/Berlin") -> reading.Parsed:
    return reading.parse(data, default_zone=zone, limit=5000)


@pytest.mark.parametrize("name", SAMPLES)
def test_round_trip_keeps_times_rules_exceptions_and_attendees(name: str) -> None:
    first = _read_back(sample(name))
    data = b"".join(writing.calendar_ics([_export(d) for d in first.events], name="Export"))
    second = _read_back(data, zone="Asia/Tokyo")  # another zone: nothing floats
    assert second.problems == Counter()
    assert [d.uid for d in second.events] == [d.uid for d in first.events]
    for before, after in zip(first.events, second.events, strict=True):
        assert effective(after) == effective(before)
        assert after.content == before.content
        assert after.organiser == before.organiser
        assert after.alarms == before.alarms
        assert after.series.rrule == before.series.rrule
        assert after.series.tzid == before.series.tzid
        assert [o.content for o in after.overrides] == [o.content for o in before.overrides]


def test_a_built_event_round_trips_with_every_field() -> None:
    draft = EventDraft(
        uid="built@herd.test",
        series=Series(
            start=datetime(2026, 3, 27, 2, 30),  # the next day's 02:30 lies in the gap
            duration=timedelta(minutes=45),
            tzid="Europe/Berlin",
            all_day=False,
            rrule="FREQ=DAILY;COUNT=4",
            rdates=(datetime(2026, 4, 5, 12, 0),),
            exdates=(datetime(2026, 3, 28, 2, 30),),
        ),
        content=Content(
            title="Alles, mit; Zeichen \\ und\nZeilen",
            location="Ort: hier",
            description="Ä" * 200,
            status=Status.TENTATIVE,
            visibility=Visibility.PRIVATE,
            busy=False,
            sequence=7,
            attendees=(
                AttendeeDraft(
                    "a@example.org", 'Name "mit" Zeichen; ja', Role.OPTIONAL, Response.DECLINED
                ),
                AttendeeDraft("b@example.org", None, Role.REQUIRED, Response.TENTATIVE),
            ),
        ),
        organiser="o@example.org",
        overrides=(
            OverrideDraft(
                recurrence_id=datetime(2026, 3, 30, 2, 30),
                series=Series(datetime(2026, 3, 30, 18), timedelta(hours=2), "Asia/Kolkata", False),
                content=Content(title="verschoben", sequence=8),
            ),
        ),
        alarms=(0, 40320),
    )
    data = writing.event_ics(ExportEvent.of(draft, stamp=STAMP))
    (back,) = _read_back(data).events
    assert back == draft


def test_writing_is_strict() -> None:
    zoned = EventDraft(
        uid="strict@herd.test",
        series=Series(
            datetime(2026, 10, 24, 9),
            timedelta(hours=1),
            "Europe/Berlin",
            False,
            rrule="FREQ=DAILY;UNTIL=20261030T080000Z",
            exdates=(datetime(2026, 10, 26, 9),),
            rdates=(datetime(2026, 11, 2, 9),),
        ),
        content=Content(title="t"),
    )
    text = writing.event_ics(ExportEvent.of(zoned, stamp=STAMP)).decode()
    lines = text.split("\r\n")
    assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")
    assert all(len(line.encode()) <= 75 for line in lines)
    assert "DTSTART;TZID=Europe/Berlin:20261024T090000" in lines
    assert "DTEND;TZID=Europe/Berlin:20261024T100000" in lines
    assert "RRULE:FREQ=DAILY;UNTIL=20261030T080000Z" in lines
    assert "EXDATE;TZID=Europe/Berlin:20261026T090000" in lines
    assert "RDATE;TZID=Europe/Berlin:20261102T090000" in lines
    assert "DTSTAMP:20261118T120000Z" in lines
    assert lines[:3] == [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//to-herd-cats-ai//calendar//EN",
    ]
    assert "BEGIN:VTIMEZONE" in lines and "TZID:Europe/Berlin" in lines
    assert lines.index("BEGIN:VTIMEZONE") < lines.index("BEGIN:VEVENT")

    all_day = EventDraft(
        uid="day@herd.test",
        series=Series(
            datetime(2026, 7, 1),
            timedelta(days=2),
            None,
            True,
            rrule="FREQ=WEEKLY;UNTIL=20260729",
            exdates=(datetime(2026, 7, 8),),
        ),
        content=Content(busy=True),
    )
    lines = writing.event_ics(ExportEvent.of(all_day, stamp=STAMP)).decode().split("\r\n")
    assert "DTSTART;VALUE=DATE:20260701" in lines
    assert "DTEND;VALUE=DATE:20260703" in lines
    assert "EXDATE;VALUE=DATE:20260708" in lines
    assert "RRULE:FREQ=WEEKLY;UNTIL=20260729" in lines
    assert "TRANSP:OPAQUE" in lines
    assert "BEGIN:VTIMEZONE" not in lines

    in_utc = EventDraft(
        uid="utc@herd.test",
        series=Series(
            datetime(2026, 7, 1, 8), timedelta(0), "UTC", False, rrule="FREQ=DAILY;COUNT=2"
        ),
        content=Content(),
    )
    lines = writing.event_ics(ExportEvent.of(in_utc, stamp=STAMP)).decode().split("\r\n")
    assert "DTSTART:20260701T080000Z" in lines and "BEGIN:VTIMEZONE" not in lines


def test_an_end_in_a_doubled_hour_is_written_as_a_duration() -> None:
    # 00:30 CEST + 3 h on 25 October 2026 ends at 02:30 CET, the second 02:30 of that
    # night: as DTEND it would read back as the first one, an hour too early.
    draft = EventDraft(
        uid="fold@herd.test",
        series=Series(datetime(2026, 10, 25, 0, 30), timedelta(hours=3), "Europe/Berlin", False),
        content=Content(),
    )
    lines = writing.event_ics(ExportEvent.of(draft, stamp=STAMP)).decode().split("\r\n")
    assert "DURATION:PT3H" in lines
    assert not any(line.startswith("DTEND") for line in lines)
    (back,) = _read_back("\r\n".join(lines).encode()).events
    assert effective(back) == effective(draft)


def test_a_calendar_streams_one_vtimezone_per_zone() -> None:
    events = [
        EventDraft(
            uid=f"e{n}@herd.test",
            series=Series(datetime(2026, 7, n + 1, 9), timedelta(hours=1), zone, False),
            content=Content(title=f"e{n}"),
        )
        for n, zone in enumerate(["Europe/Berlin", "America/New_York", "Europe/Berlin"])
    ]
    chunks = list(
        writing.calendar_ics((ExportEvent.of(e, stamp=STAMP) for e in events), name="Team; Herd")
    )
    assert len(chunks) > 3  # a stream, not one buffer
    text = b"".join(chunks).decode()
    assert text.count("BEGIN:VTIMEZONE") == 2
    assert "X-WR-CALNAME:Team\\; Herd" in text and "\r\nNAME:Team\\; Herd\r\n" in text
    assert text.endswith("END:VCALENDAR\r\n")


def test_a_redacted_event_writes_no_content() -> None:
    secret = "Geheimes Projekt Falke"
    draft = EventDraft(
        uid="falke-board-meeting@herd.test",
        series=Series(
            datetime(2026, 7, 1, 9),
            timedelta(hours=1),
            "Europe/Berlin",
            False,
            rrule="FREQ=DAILY;COUNT=3",
        ),
        content=Content(
            title=secret,
            location=secret,
            description=secret,
            visibility=Visibility.PRIVATE,
            attendees=(
                AttendeeDraft("falke@example.org", secret, Role.REQUIRED, Response.ACCEPTED),
            ),
        ),
        organiser="falke@example.org",
        overrides=(
            OverrideDraft(
                recurrence_id=datetime(2026, 7, 2, 9),
                series=Series(datetime(2026, 7, 2, 15), timedelta(hours=1), "Europe/Berlin", False),
                content=Content(title=secret, description=secret),
            ),
        ),
        alarms=(10,),
    )
    data = writing.event_ics(ExportEvent.of(draft, stamp=STAMP, redacted=True))
    text = data.decode()
    for leak in (
        "Falke",
        "falke",
        "SUMMARY",
        "LOCATION",
        "DESCRIPTION",
        "ATTENDEE",
        "ORGANIZER",
        "VALARM",
    ):
        assert leak not in text
    (back,) = _read_back(data).events
    assert effective(back) == effective(draft)  # the time stays, busy and private
    assert back.content.busy and back.content.visibility is Visibility.PRIVATE
    assert back.uid != draft.uid and back.uid == _read_back(data).events[0].uid  # stable, opaque
