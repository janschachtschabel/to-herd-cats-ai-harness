"""The written VTIMEZONE keeps every change `tzdata` has (re-check M10 Task 7a, RC7a-6):
its history is built from the zone's own transitions, so a change undone within weeks
(Casablanca's and El Aaiún's Ramadan pauses, Gaza's and Hebron's, Fiji's 2020/21, Cairo
2010, Jerusalem 1980, Shanghai 1949, Argentina 2004, north-east Brazil 2000) is kept.

Read back under another TZID, so no reader can take the IANA name instead: with our
reader (`vtimezone.definition`) and with `icalendar`'s `to_tz()`. Pacific/Apia: a
`dateutil`-based reader such as `to_tz()` raises on 30 December 2011, where the offset
jumps by 24 hours; nothing a writer can put in a VTIMEZONE avoids that, so Apia is read
with ours only."""

import hashlib
from datetime import UTC, date, datetime, timedelta

import icalendar
import pytest

from app.modules.calendars import zones
from app.modules.calendars.ical import lines, vtimezone_out
from app.modules.calendars.ical.vtimezone import definition

AFFECTED = [
    "Africa/Casablanca",
    "Africa/El_Aaiun",
    "Asia/Gaza",
    "Asia/Hebron",
    "Pacific/Fiji",
    "Africa/Cairo",
    "Asia/Jerusalem",
    "Asia/Shanghai",
    "America/Argentina/San_Luis",
    "America/Fortaleza",
    "Pacific/Apia",
]
_SHORT = timedelta(days=60)


def _short_periods(tzid: str) -> list[datetime]:
    """Noon (wall time) in the middle of every period between two changes of `tzid`
    shorter than 60 days, 1900 to 2399: found day by day, independently of the writer."""
    zone = zones.zone(tzid)
    changes: list[datetime] = []
    day = datetime(1900, 1, 1, 12, tzinfo=UTC)
    before = day.astimezone(zone).utcoffset()
    while day.year < 2400:
        day += timedelta(days=1)
        offset = day.astimezone(zone).utcoffset()
        if offset != before:
            changes.append(day)
            before = offset
    middles = [
        a + (b - a) / 2 for a, b in zip(changes, changes[1:], strict=False) if b - a < _SHORT
    ]
    return [m.astimezone(zone).replace(tzinfo=None, hour=12, minute=0, second=0) for m in middles]


def _name(tzid: str) -> str:
    """A TZID no reader knows, one per zone (`icalendar` caches zones by TZID for the
    whole process)."""
    return "Renamed-" + hashlib.sha256(tzid.encode()).hexdigest()[:12]


def _renamed(tzid: str) -> bytes:
    return vtimezone_out.vtimezone(tzid).replace(
        f"TZID:{tzid}".encode(), f"TZID:{_name(tzid)}".encode()
    )


@pytest.mark.parametrize("tzid", AFFECTED)
def test_a_short_period_reads_back_as_tzdata_has_it_in_our_reader(tzid: str) -> None:
    walls = _short_periods(tzid)
    if tzid != "Pacific/Apia":
        assert walls, "the zone has short periods"
    tops, _ = lines.read(b"BEGIN:VCALENDAR\r\n" + _renamed(tzid) + b"END:VCALENDAR\r\n")
    found = definition(tops[0].children[0])
    assert found is not None
    zone = zones.zone(tzid)
    assert [w for w in walls if found.offset_at(w) != zone.utcoffset(w)] == []


@pytest.mark.parametrize("tzid", [z for z in AFFECTED if z != "Pacific/Apia"])
def test_a_short_period_reads_back_as_tzdata_has_it_in_icalendars_reader(tzid: str) -> None:
    data = b"BEGIN:VCALENDAR\r\n" + _renamed(tzid) + b"END:VCALENDAR\r\n"
    (component,) = icalendar.Calendar.from_ical(data).walk("VTIMEZONE")
    assert str(component["TZID"]) == _name(tzid)
    assert isinstance(component, icalendar.Timezone)
    theirs = component.to_tz()
    zone = zones.zone(tzid)
    wrong = [
        w for w in _short_periods(tzid) if w.replace(tzinfo=theirs).utcoffset() != zone.utcoffset(w)
    ]
    assert wrong == []


def test_a_zone_without_changes_has_one_observance() -> None:
    tops, _ = lines.read(
        b"BEGIN:VCALENDAR\r\n" + vtimezone_out.vtimezone("Etc/GMT-3") + b"END:VCALENDAR\r\n"
    )
    found = definition(tops[0].children[0])
    assert found is not None
    for day in (date(1900, 1, 1), date(2026, 7, 1), date(2399, 12, 31)):
        assert found.offset_at(datetime.combine(day, datetime.min.time())) == timedelta(hours=3)
