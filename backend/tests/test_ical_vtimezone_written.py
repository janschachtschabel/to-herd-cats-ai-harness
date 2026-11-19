"""The VTIMEZONE written for a zone covers every event written in it (review M10 Task
7a, R7a-11): clients that follow the definition rather than the IANA name (Outlook)
place an event of 1950, 2050 or an endless series' occurrence in 2300 as `tzdata` does.
The definition is read back with our own reader (`vtimezone.definition`), never with
`icalendar`'s zone cache."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.calendars import zones
from app.modules.calendars.ical import lines, writing
from app.modules.calendars.ical.drafts import Content, ExportEvent
from app.modules.calendars.ical.vtimezone import Definition, definition
from app.modules.calendars.recurrence import Series

NOW = datetime(2026, 11, 19, tzinfo=UTC)
SPECIAL = [
    "Europe/Berlin",
    "America/New_York",
    "America/Santiago",  # changes at 24:00 on a Saturday
    "America/Nuuk",  # at -1:00 on the last Sunday
    "Asia/Jerusalem",  # on the Friday before the last Sunday
    "Australia/Lord_Howe",  # half an hour
    "Antarctica/Troll",  # two hours
    "Europe/Dublin",  # negative summer time in tzdata
    "Africa/Casablanca",  # changes by the moon until 2087
    "Pacific/Apia",  # no changes any more
    "Asia/Kathmandu",
]


def _event(tzid: str, year: int, uid: str, rrule: str | None = None) -> ExportEvent:
    series = Series(datetime(year, 7, 1, 9), timedelta(hours=1), tzid, False, rrule=rrule)
    return ExportEvent(uid=uid, series=series, content=Content(), stamp=NOW)


def _definitions(data: bytes) -> dict[str, Definition]:
    tops, _ = lines.read(data)
    found: dict[str, Definition] = {}
    for child in tops[0].children:
        if child.name == "VTIMEZONE":
            tzid = child.first("TZID")
            parsed = definition(child)
            assert tzid is not None and parsed is not None
            found[tzid.text] = parsed
    return found


def _noons(years: list[int]) -> list[datetime]:
    return [datetime(y, m, d, 12) for y in years for m in range(1, 13) for d in (1, 9, 17, 25)]


@pytest.mark.parametrize("tzid", sorted({*SPECIAL, *sorted(zones.names() - {"UTC"})[::40]}))
def test_the_written_vtimezone_follows_tzdata_for_every_event_in_the_stream(tzid: str) -> None:
    events = [
        _event(tzid, 2026, "first"),
        _event(tzid, 2050, "later"),
        _event(tzid, 1950, "earlier"),
        _event(tzid, 2026, "endless", rrule="FREQ=YEARLY"),
    ]
    data = b"".join(writing.calendar_ics(events, name="x", now=NOW))
    assert data.count(b"BEGIN:VTIMEZONE") == 1
    found = _definitions(data)[tzid]
    zone = zones.zone(tzid)
    wrong = [
        wall
        for wall in _noons([1950, 1975, 2026, 2037, 2038, 2050, 2100, 2300, 2399])
        if found.offset_at(wall) != zone.utcoffset(wall)
    ]
    assert wrong == []
