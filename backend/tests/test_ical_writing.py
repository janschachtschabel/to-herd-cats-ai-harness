"""Writing takes nothing on trust (plan M10, Global Constraints: what comes from outside
is untrusted): no text, name or address can end a line and start a property of its own,
and a stamp without a zone is refused rather than read in the process's zone."""

from datetime import datetime, timedelta

import pytest

from app.modules.calendars.ical import reading, writing
from app.modules.calendars.ical.drafts import AttendeeDraft, Content, EventDraft, ExportEvent
from app.modules.calendars.recurrence import Series
from tests.support.ical_occurrences import utc

SERIES = Series(datetime(2026, 7, 1, 9), timedelta(hours=1), "Europe/Berlin", False)


def test_written_texts_and_addresses_cannot_break_lines() -> None:
    draft = EventDraft(
        uid="uid\rwith\nbreaks",
        series=SERIES,
        content=Content(
            title="a\rb",
            description="x\r\nSUMMARY:evil\rmore\x00",
            attendees=(
                AttendeeDraft("a@b.org\r\nATTENDEE:mailto:evil@x.org"),
                AttendeeDraft("ok@x.org", "Na\r\nme\x07"),
            ),
        ),
        organiser="o@x.org\nX-INJECTED:1",
        alarms=(5,),
    )
    data = writing.event_ics(ExportEvent.of(draft, stamp=utc(2026, 11, 19)))
    assert b"\r" not in data.replace(b"\r\n", b"") and b"\n" not in data.replace(b"\r\n", b"")
    lines = data.decode().split("\r\n")
    assert not any(
        line.startswith(("SUMMARY:evil", "ATTENDEE:mailto:evil", "X-INJECTED")) for line in lines
    )
    (back,) = reading.parse(data, default_zone="Europe/Berlin", limit=10).events
    assert back.uid == "uid\nwith\nbreaks"
    assert back.content.title == "a\nb"
    assert back.content.description == "x\nSUMMARY:evil\nmore"
    assert back.content.attendees == (AttendeeDraft("ok@x.org", "Na me"),)
    assert back.organiser is None  # an address that is none is not written


def test_a_stamp_without_a_zone_is_refused() -> None:
    draft = EventDraft(uid="u", series=SERIES, content=Content())
    with pytest.raises(ValueError, match="aware"):
        ExportEvent.of(draft, stamp=datetime(2026, 11, 19))
