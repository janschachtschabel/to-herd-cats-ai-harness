"""Zones of the calendar (plan M10 decision 6): IANA names only, a wall time that does
not exist moves on by the gap, one that exists twice takes the first."""

from datetime import UTC, date, datetime

import pytest

from app.modules.calendars import zones


def test_zone_knows_iana_names_only() -> None:
    assert zones.zone("Europe/Berlin").key == "Europe/Berlin"
    for name in ("", "Mars/Olympus", "localtime", "../etc/passwd", "W. Europe Standard Time"):
        with pytest.raises(zones.ZoneUnknown):
            zones.zone(name)


@pytest.mark.parametrize(
    ("wall", "tzid", "instant"),
    [
        # an ordinary summer time
        (datetime(2026, 6, 1, 9, 0), "Europe/Berlin", datetime(2026, 6, 1, 7, 0, tzinfo=UTC)),
        # spring gap in Berlin (02:00 → 03:00): 02:30 moves on by the gap, to 03:30 CEST
        (datetime(2026, 3, 29, 2, 30), "Europe/Berlin", datetime(2026, 3, 29, 1, 30, tzinfo=UTC)),
        # autumn in Berlin: 02:30 twice, the first (CEST)
        (datetime(2026, 10, 25, 2, 30), "Europe/Berlin", datetime(2026, 10, 25, 0, 30, tzinfo=UTC)),
        # New York's gap (02:00 → 03:00 on 8 March 2026)
        (datetime(2026, 3, 8, 2, 30), "America/New_York", datetime(2026, 3, 8, 7, 30, tzinfo=UTC)),
        # New York's doubled hour (1 November 2026): the first, EDT
        (
            datetime(2026, 11, 1, 1, 30),
            "America/New_York",
            datetime(2026, 11, 1, 5, 30, tzinfo=UTC),
        ),
        # southern hemisphere: Sydney's gap on 4 October 2026 (02:00 → 03:00)
        (
            datetime(2026, 10, 4, 2, 30),
            "Australia/Sydney",
            datetime(2026, 10, 3, 16, 30, tzinfo=UTC),
        ),
        # Sydney's doubled hour on 5 April 2026 (03:00 → 02:00): the first, AEDT
        (datetime(2026, 4, 5, 2, 30), "Australia/Sydney", datetime(2026, 4, 4, 15, 30, tzinfo=UTC)),
    ],
)
def test_localise_moves_gaps_on_and_takes_the_first_of_two(
    wall: datetime, tzid: str, instant: datetime
) -> None:
    localised = zones.localise(wall, tzid)
    assert localised == instant
    assert localised.utcoffset() == UTC.utcoffset(None)


def test_localise_takes_wall_times_and_wall_gives_them() -> None:
    with pytest.raises(ValueError, match="naive"):
        zones.localise(datetime(2026, 6, 1, 9, tzinfo=UTC), "Europe/Berlin")
    with pytest.raises(ValueError, match="aware"):
        zones.wall(datetime(2026, 6, 1, 9), "Europe/Berlin")
    assert zones.wall(datetime(2026, 6, 1, 7, tzinfo=UTC), "Europe/Berlin") == datetime(
        2026, 6, 1, 9
    )
    # the first 02:30 of the doubled hour comes back as 02:30
    first = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert zones.wall(first, "Europe/Berlin") == datetime(2026, 10, 25, 2, 30)


def test_all_day_bounds_are_midnights_in_utc() -> None:
    assert zones.all_day_bounds(date(2026, 1, 31), date(2026, 2, 1)) == (
        datetime(2026, 1, 31, tzinfo=UTC),
        datetime(2026, 2, 2, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="before"):
        zones.all_day_bounds(date(2026, 2, 2), date(2026, 2, 1))
