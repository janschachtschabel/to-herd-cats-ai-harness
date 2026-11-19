"""Reading never raises for a file's sake (plan M10, Review Focus 4: broken zones,
lines without end, odd forms), and what it reads writes back to the same occurrences.
Seeded: the sample files mangled by deleted bytes, inserted tokens, shuffled lines
and random bytes."""

import random
from datetime import UTC, datetime

from app.modules.calendars.ical import reading, writing
from app.modules.calendars.ical.drafts import ExportEvent
from tests.support.ical_occurrences import DATA, effective

ROUNDS = 600
TOKENS = [
    b";",
    b":",
    b",",
    b'"',
    b"\\",
    b"=",
    b"\r\n",
    b"\r\n ",
    b"TZID=",
    b"VALUE=DATE",
    b"Z",
    b"T",
    b"-",
    b"9",
    b"\x00",
    b"\xff",
    b"BEGIN:VEVENT\r\n",
    b"END:VEVENT\r\n",
    b"END:VCALENDAR\r\n",
    b"RRULE:FREQ=YEARLY;BYDAY=-1SU\r\n",
    b"RECURRENCE-ID:20261102T100000\r\n",
    b"RANGE=THISANDFUTURE",
    b"DURATION:P1W\r\n",
    b"BEGIN:VALARM\r\nTRIGGER:-P1D\r\nEND:VALARM\r\n",
    b"EXDATE;VALUE=PERIOD:20260101T000000Z/PT1H\r\n",
    b"BEGIN:VTIMEZONE\r\nTZID:X\r\nEND:VTIMEZONE\r\n",
]


def _mangle(data: bytes, rng: random.Random) -> bytes:
    out = bytearray(data)
    for _ in range(rng.randint(1, 3)):
        choice = rng.random()
        at = rng.randrange(len(out) + 1)
        if choice < 0.3:
            del out[at : at + rng.randint(1, 20)]
        elif choice < 0.75:
            out[at:at] = rng.choice(TOKENS)
        elif choice < 0.8:
            lines = bytes(out).split(b"\r\n")
            rng.shuffle(lines)
            out = bytearray(b"\r\n".join(lines))
        else:
            out[at : at + 1] = bytes([rng.randrange(256)])
    return bytes(out)


def test_mangled_files_never_raise_and_read_back_alike() -> None:
    rng = random.Random(20261119)
    samples = [path.read_bytes() for path in sorted(DATA.glob("*.ics"))]
    stamp = datetime(2026, 11, 19, tzinfo=UTC)
    read_events = 0
    for _ in range(ROUNDS):
        parsed = reading.parse(
            _mangle(rng.choice(samples), rng), default_zone="Europe/Berlin", limit=50
        )
        exported = [ExportEvent.of(draft, stamp=stamp) for draft in parsed.events]
        back = reading.parse(
            b"".join(writing.calendar_ics(exported, name="x")), default_zone="Asia/Tokyo", limit=50
        )
        assert not back.problems
        for before, after in zip(parsed.events, back.events, strict=True):
            assert effective(after) == effective(before)
            assert (after.content, after.alarms, after.organiser) == (
                before.content,
                before.alarms,
                before.organiser,
            )
        read_events += len(parsed.events)
    assert read_events > ROUNDS // 2  # many mangled files still hold events
