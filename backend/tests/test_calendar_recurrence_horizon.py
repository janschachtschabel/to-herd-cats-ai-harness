"""Series that reach the end of 2399 (review M10 task 3c, R3c-6). `dateutil` runs
7,600 years ahead of us, so our 31 December 2399 is its 31 December 9999; a weekly
rule builds its whole week before it looks at a bound, and a week holding that day
reaches into the year 10000. Such a series must neither raise nor vanish from a
window: it ends where the years of the calendar end."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.calendars import recurrence
from app.modules.calendars.recurrence import Series
from app.modules.calendars.recurrence_jump import Counter

HOUR = timedelta(hours=1)
END = datetime(2400, 1, 1, tzinfo=UTC)


def _utc(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=UTC)  # type: ignore[misc]


def _weekly_until_the_end(start: datetime, interval: int, until: datetime) -> list[datetime]:
    """The expected starts, by plain stepping (no `dateutil`)."""
    found, at = [], start
    while at < until:
        found.append(at)
        at += timedelta(weeks=interval)
    return found


@pytest.mark.parametrize(
    ("rule", "start", "window_from"),
    [
        ("FREQ=WEEKLY", datetime(2399, 11, 9, 9), _utc(2399, 12, 20)),
        ("FREQ=WEEKLY", datetime(2399, 12, 26, 9), _utc(2399, 12, 20)),
        ("FREQ=WEEKLY;INTERVAL=14", datetime(2399, 10, 2, 9), _utc(2399, 10, 1)),
        ("FREQ=WEEKLY;BYDAY=MO,FR;WKST=SU", datetime(2399, 12, 1, 9), _utc(2399, 12, 20)),
        ("FREQ=WEEKLY;BYDAY=MO,TU;BYSETPOS=-1", datetime(2399, 11, 30, 9), _utc(2399, 12, 1)),
        ("FREQ=WEEKLY;COUNT=40", datetime(2399, 11, 9, 9), _utc(2399, 12, 20)),
    ],
)
def test_a_weekly_series_reaching_the_end_of_2399_keeps_its_occurrences(
    rule: str, start: datetime, window_from: datetime
) -> None:
    series = Series(start, HOUR, "UTC", False, rule)
    found = recurrence.occurrences(series, window_from, END)
    assert found, rule  # the series does not vanish from the window
    assert all(window_from - HOUR < o.start < END for o in found)
    for occurrence in found:
        assert recurrence.is_occurrence(series, occurrence.recurrence_id)
    last = found[-1].recurrence_id
    assert recurrence.next_after(series, found[-1].start) is None
    assert not recurrence.is_occurrence(series, last + timedelta(days=1))


def test_the_plain_weekly_case_matches_plain_stepping() -> None:
    start = datetime(2399, 11, 9, 9)
    series = Series(start, HOUR, "UTC", False, "FREQ=WEEKLY")
    found = recurrence.occurrences(series, _utc(2399, 11, 1), END)
    expected = _weekly_until_the_end(start, 1, datetime(2400, 1, 1))
    assert [o.recurrence_id for o in found] == expected
    assert expected[-1] == datetime(2399, 12, 28, 9)


def test_a_check_and_the_endless_end_reach_the_horizon_without_raising() -> None:
    series = Series(datetime(2399, 12, 30, 9), HOUR, "UTC", False, "FREQ=WEEKLY")
    assert recurrence.check_series(series) == datetime(2399, 12, 30, 9)
    assert recurrence.last_end(series) is None  # endless: no end to give
    counted = Series(datetime(2399, 12, 30, 9), HOUR, "UTC", False, "FREQ=WEEKLY;COUNT=5")
    assert recurrence.last_end(counted) == _utc(2399, 12, 30, 10)  # one fits before 2400
    counter = Counter()
    assert list(recurrence.walls(series, datetime(2399, 12, 1), recurrence.HORIZON, counter)) == [
        datetime(2399, 12, 30, 9)
    ]


def _days(*days: int) -> list[datetime]:
    return [datetime(2399, 12, day, 9) for day in days]


@pytest.mark.parametrize(
    ("rule", "start", "expected"),
    [
        # BYSETPOS takes the whole week's set first: Monday 27 December is the first of
        # the last week's set {Monday 27, Sunday 2 January 2400}.
        ("FREQ=WEEKLY;BYDAY=MO,SU;BYSETPOS=1", datetime(2399, 12, 6, 9), _days(13, 20, 27)),
        # Two positions: `dateutil` builds both days of the set before it yields one,
        # so the last week's Monday was lost with its Sunday in the year 10000.
        (
            "FREQ=WEEKLY;BYDAY=MO,SU;BYSETPOS=1,-1",
            datetime(2399, 12, 6, 9),
            _days(13, 19, 20, 26, 27),
        ),
        # Friday 31 December, the last day of the calendar's years.
        ("FREQ=WEEKLY;BYDAY=FR,SU", datetime(2399, 12, 5, 9), _days(17, 19, 24, 26, 31)),
        # Every other week from Tuesday 14 (weeks Tuesday to Monday): the last one,
        # 28 December to 3 January, is scanned again in phase.
        (
            "FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,SU;BYSETPOS=1,2;WKST=TU",
            datetime(2399, 12, 14, 9),
            _days(14, 19, 28),
        ),
        (
            "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,SU;WKST=TU",
            datetime(2399, 12, 13, 9),
            _days(13, 26, 27),
        ),
    ],
)
def test_the_last_week_of_2399_keeps_every_occurrence(
    rule: str, start: datetime, expected: list[datetime]
) -> None:
    series = Series(start, HOUR, "UTC", False, rule)
    found = recurrence.occurrences(series, _utc(2399, 12, 13), END)
    assert [o.recurrence_id for o in found] == expected
    assert all(recurrence.is_occurrence(series, wall) for wall in expected)
    assert recurrence.next_after(series, found[-1].start) is None
