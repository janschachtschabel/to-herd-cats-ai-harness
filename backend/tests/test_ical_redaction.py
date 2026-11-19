"""What a reader who sees an event only as busy gets (review M10 Task 7a, R7a-5, R7a-13,
R7a-14; decision 3: "nur Zeit und Belegt"): times, TRANSP, CLASS:PRIVATE, a status that
says only whether the time is taken, the moment of writing as DTSTAMP, and a UID nobody
can confirm a guess against."""

from datetime import datetime, timedelta

import pytest

from app.modules.calendars.ical import opaque, reading, writing
from app.modules.calendars.ical.drafts import (
    AttendeeDraft,
    Content,
    ExportEvent,
    ExportOverride,
    Status,
)
from app.modules.calendars.recurrence import Series
from tests.support.ical_occurrences import utc

KEY = opaque.key_from_secret("an installation's secret key, 32+ characters")
CHANGED = utc(2026, 3, 14, 15, 9, 26)  # the event's last change: never told
NOW = utc(2026, 11, 19, 8)
SERIES = Series(
    datetime(2026, 7, 1, 9), timedelta(hours=1), "Europe/Berlin", False, rrule="FREQ=DAILY;COUNT=3"
)
SECRET = Content(
    title="Selbsthilfegruppe",
    location="Praxis Dr. Falke",
    description="Raum 3",
    status=Status.TENTATIVE,
    sequence=7,
    attendees=(AttendeeDraft("falke@example.org", "Dr. Falke"),),
)
BUSY_ONLY = {"UID", "DTSTAMP", "DTSTART", "DTEND", "DURATION", "RRULE", "RDATE", "EXDATE"} | {
    "RECURRENCE-ID",
    "STATUS",
    "TRANSP",
    "CLASS",
}


def _vevents(data: bytes) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in data.decode().split("\r\n"):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            found.append(current)
            current = None
        elif current is not None and line and not line.startswith(" "):
            name, _, value = line.partition(":")
            current[name.split(";")[0]] = value
    return found


def _event(**changes: object) -> ExportEvent:
    fields: dict[str, object] = {
        "uid": "event_305123456@meetup.example",
        "series": SERIES,
        "content": SECRET,
        "stamp": CHANGED,
        "organiser": "falke@example.org",
        "alarms": (15,),
    }
    fields.update(changes)
    return ExportEvent(**fields)  # type: ignore[arg-type]


def _override(redacted: bool) -> ExportOverride:
    moved = Series(datetime(2026, 7, 2, 15), timedelta(hours=1), "Europe/Berlin", False)
    return ExportOverride(datetime(2026, 7, 2, 9), moved, SECRET, redacted=redacted)


def test_a_redacted_event_writes_only_what_busy_time_needs() -> None:
    uid = opaque.opaque_uid(
        "event_305123456@meetup.example", key=KEY, purpose=opaque.Purpose.FEED, audience="feed-1"
    )
    event = _event(redacted=True, opaque_uid=uid, overrides=(_override(True),))
    data = writing.event_ics(event, now=NOW)
    master, override = _vevents(data)
    for part in (master, override):
        assert set(part) <= BUSY_ONLY, set(part) - BUSY_ONLY
        assert part["UID"] == uid
        assert part["DTSTAMP"] == "20261119T080000Z"  # the moment of writing
        assert part["STATUS"] == "CONFIRMED"  # tentative is not told
        assert part["CLASS"] == "PRIVATE"
    assert b"20260314" not in data


def test_a_redacted_tombstone_still_frees_its_time() -> None:
    cancelled = Content(title="Falke", status=Status.CANCELLED)
    uid = opaque.opaque_uid("u", key=KEY, purpose=opaque.Purpose.FEED, audience="feed-1")
    (master,) = _vevents(
        writing.event_ics(_event(content=cancelled, redacted=True, opaque_uid=uid), now=NOW)
    )
    assert master["STATUS"] == "CANCELLED"


def test_a_redacted_event_needs_its_opaque_uid() -> None:
    with pytest.raises(ValueError, match="opaque UID"):
        _event(redacted=True)


def test_an_override_has_a_decision_of_its_own() -> None:
    # the series visible, one occurrence only busy (its own visibility, I6)
    data = writing.event_ics(_event(overrides=(_override(True),)), now=NOW)
    master, override = _vevents(data)
    assert master["SUMMARY"] == "Selbsthilfegruppe" and master["DTSTAMP"] == "20260314T150926Z"
    assert set(override) <= BUSY_ONLY and override["DTSTAMP"] == "20261119T080000Z"
    assert override["UID"] == master["UID"] == "event_305123456@meetup.example"
    # the series only busy, one occurrence visible: under the opaque UID, no last change
    uid = opaque.opaque_uid(
        "event_305123456@meetup.example", key=KEY, purpose=opaque.Purpose.FEED, audience="feed-1"
    )
    data = writing.event_ics(
        _event(redacted=True, opaque_uid=uid, overrides=(_override(False),)), now=NOW
    )
    master, override = _vevents(data)
    assert set(master) <= BUSY_ONLY
    assert override["SUMMARY"] == "Selbsthilfegruppe" and override["UID"] == uid
    assert override["DTSTAMP"] == "20261119T080000Z"
    (back,) = reading.parse(data, default_zone="Europe/Berlin", limit=10).events
    assert [o.content.title for o in back.overrides] == ["Selbsthilfegruppe"]


def test_the_opaque_uid_is_keyed_per_reader() -> None:
    uid = "event_305123456@meetup.example"
    first = opaque.opaque_uid(uid, key=KEY, purpose=opaque.Purpose.FEED, audience="feed-1")
    assert first == opaque.opaque_uid(
        uid, key=KEY, purpose=opaque.Purpose.FEED, audience="feed-1"
    )  # stable
    assert first != opaque.opaque_uid(
        uid, key=KEY, purpose=opaque.Purpose.FEED, audience="feed-2"
    )  # not joinable
    other = opaque.key_from_secret("another installation's secret key, 32+ chars")
    assert first != opaque.opaque_uid(
        uid, key=other, purpose=opaque.Purpose.FEED, audience="feed-1"
    )
    assert first.endswith("@busy.invalid") and len(first.split("@")[0]) == 32
    with pytest.raises(ValueError):
        opaque.opaque_uid(uid, key=b"short", purpose=opaque.Purpose.FEED, audience="feed-1")


@pytest.mark.parametrize("separator", [" ", " ", "\x85", "\x0b", "\x0c", "\x1c"])
def test_no_line_separator_reaches_the_file(separator: str) -> None:
    """R7a-12: a reader that splits on Unicode line separators (`str.splitlines`,
    JavaScript) must not see a property begin inside a text or a UID."""
    evil = f"x{separator}ATTENDEE:mailto:evil@x.org"
    content = Content(title=evil, location=evil, description=evil)
    data = writing.event_ics(_event(uid=f"u{separator}X-EVIL:1", content=content), now=NOW)
    for line in data.decode().splitlines():
        assert not line.startswith(("ATTENDEE:mailto:evil", "X-EVIL:1"))
    (back,) = reading.parse(data, default_zone="Europe/Berlin", limit=10).events
    assert back.uid == "uX-EVIL:1"
    assert separator not in back.content.title
