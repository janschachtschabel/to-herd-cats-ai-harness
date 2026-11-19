"""Which zone a file's own VTIMEZONE means when several fit (review M10 Task 7a,
R7a-10): compared across the years the event spans, then the zone the definition names,
then the one that has followed the definition longest."""

from collections import Counter

import pytest

from app.modules.calendars.ical import reading, zones

# The United States' rules since 2007, as Outlook writes them (from 1601, no location).
US_EASTERN = """BEGIN:VTIMEZONE
TZID:{tzid}
BEGIN:STANDARD
DTSTART:16011104T020000
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:16010311T020000
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
END:VTIMEZONE
"""


def _calendar(*parts: str) -> bytes:
    return ("BEGIN:VCALENDAR\nVERSION:2.0\n" + "".join(parts) + "END:VCALENDAR\n").encode()


def _event(tzid: str, start: str, extra: str = "") -> str:
    return f'BEGIN:VEVENT\nUID:u\nDTSTART;TZID="{tzid}":{start}\nDURATION:PT1H\n{extra}END:VEVENT\n'


def _zones(data: bytes) -> tuple[list[str | None], Counter[str]]:
    parsed = reading.parse(data, default_zone="Europe/Berlin", limit=10)
    return [d.series.tzid for d in parsed.events], parsed.problems


@pytest.mark.parametrize("tzid", ["Customized Time Zone", "(UTC-05:00) Eastern Time (US & Canada)"])
def test_us_eastern_rules_mean_new_york(tzid: str) -> None:
    """Grand Turk, Havana, Indianapolis and Port-au-Prince fit 2026 too; New York has
    followed these rules longest."""
    data = _calendar(US_EASTERN.format(tzid=tzid), _event(tzid, "20260710T090000"))
    assert _zones(data) == (["America/New_York"], Counter())


def test_a_series_that_began_before_todays_rules_finds_its_zone() -> None:
    """In 2005 no zone had the rules of 2007; the years the series spans have."""
    tzid = "Customized Time Zone"
    data = _calendar(
        US_EASTERN.format(tzid=tzid), _event(tzid, "20050606T100000", "RRULE:FREQ=WEEKLY\n")
    )
    assert _zones(data) == (["America/New_York"], Counter())


def test_a_single_event_in_a_year_no_zone_fits_stays_unknown() -> None:
    tzid = "Customized Time Zone"
    data = _calendar(US_EASTERN.format(tzid=tzid), _event(tzid, "20050606T100000"))
    assert _zones(data) == ([], Counter({"ical.time_zone_unknown": 1}))


def test_a_city_the_tzid_names_is_preferred() -> None:
    tzid = "Toronto rules"
    data = _calendar(US_EASTERN.format(tzid=tzid), _event(tzid, "20260710T090000"))
    assert _zones(data) == (["America/Toronto"], Counter())


def test_the_years_compared_lie_on_a_grid() -> None:
    assert zones.years(2026, 2026) == (2026,)
    assert zones.years(2005, 2399) == (2005, 2010, 2020, 2030, 2040)
    assert zones.years(1900, 2399) == (1900, 1910, 1940, 1970, 2000, 2040)
    assert len(zones.years(1900, 2040)) == zones.MAX_YEARS
