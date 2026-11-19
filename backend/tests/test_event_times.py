"""An event's times as every write path checks them (`event_times.check`, review M10
task 3a, R3a-1 and R3a-3): aware instants in the calendar's years 1900 to 2399, each
problem 422 with its code and never a 500."""

import time
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.core.errors import ValidationFailed
from app.modules.calendars.event_models import DATES_MAX
from app.modules.calendars.event_times import MAX_DURATION, Times, check

AWARE = datetime(2026, 11, 23, 10, tzinfo=UTC)


def _code(times: Times) -> str:
    with pytest.raises(ValidationFailed) as caught:
        check(times, "Europe/Berlin")
    return caught.value.code


def test_the_check_refuses_naive_and_far_times_with_a_code() -> None:
    """Import and tools hand `Times` to the service without the API's schema: a bound
    without an offset or beyond the calendar's years is a code, never a TypeError or
    an OverflowError."""
    minus_ten, plus_fourteen = timezone(timedelta(hours=-10)), timezone(timedelta(hours=14))
    cases = {
        "naive end": (Times(starts_at=AWARE, ends_at=datetime(2026, 11, 23, 11)), "invalid_time"),
        "naive start": (
            Times(starts_at=datetime(2026, 11, 23, 10), ends_at=AWARE + timedelta(hours=1)),
            "invalid_time",
        ),
        "both naive": (
            Times(starts_at=datetime(2026, 11, 23, 10), ends_at=datetime(2026, 11, 23, 11)),
            "invalid_time",
        ),
        "end near 9999": (
            Times(starts_at=AWARE, ends_at=datetime(9999, 12, 31, 23, 59, 59, tzinfo=minus_ten)),
            "time_out_of_range",
        ),
        "start in year 1": (
            Times(starts_at=datetime(1, 1, 1, tzinfo=plus_fourteen), ends_at=AWARE),
            "time_out_of_range",
        ),
        "end in 2400": (
            Times(starts_at=AWARE, ends_at=datetime(2400, 1, 1, 0, 0, 1, tzinfo=UTC)),
            "time_out_of_range",
        ),
    }
    got = {name: _code(times) for name, (times, _) in cases.items()}
    assert got == {name: f"event.{code}" for name, (_, code) in cases.items()}


def _timed(hours: float, rrule: str | None, rdates: tuple[datetime, ...] = ()) -> Times:
    start = datetime(2026, 11, 23, 9, tzinfo=UTC)
    return Times(
        starts_at=start,
        ends_at=start + timedelta(hours=hours),
        tzid="Europe/Berlin",
        rrule=rrule,
        rdates=rdates,
    )


def test_a_series_that_overlaps_itself_is_refused() -> None:
    """R3a-1: a series whose occurrences outlast the shortest gap between two of them
    would lie on top of itself (a daily one lasting six years: 2,191 at every instant)
    and close every reader's window. The gap is read on the series' wall clock, so a
    daily 24-hour shift stays allowed across a clock change."""
    refused = {
        "daily, 25 hours": _timed(25, "FREQ=DAILY"),
        "Monday and Tuesday, 2 days": _timed(48, "FREQ=WEEKLY;BYDAY=MO,TU"),
        "counted weekly, 8 days": _timed(8 * 24, "FREQ=WEEKLY;COUNT=3"),
        "an RDATE beyond the sample, inside an occurrence": _timed(
            1, "FREQ=DAILY", (datetime(2031, 6, 2, 10, 30),)
        ),
        "two RDATEs too close": _timed(
            2, None, (datetime(2026, 12, 1, 10), datetime(2026, 12, 1, 11))
        ),
        "daily until, 2 days": _timed(48, "FREQ=DAILY;UNTIL=20270101T000000Z"),
    }
    got = {name: _code(times) for name, times in refused.items()}
    assert got == dict.fromkeys(refused, "event.series_overlaps")
    for times in (
        _timed(24, "FREQ=DAILY"),  # touches the next one, through both clock changes
        _timed(24, "FREQ=WEEKLY;BYDAY=MO,TU"),
        _timed(300 * 24, "FREQ=YEARLY"),
        _timed(1, "FREQ=DAILY", (datetime(2031, 6, 2, 12),)),
        _timed(1, None, (datetime(2026, 12, 1, 10), datetime(2026, 12, 1, 11))),
    ):
        assert check(times, "Europe/Berlin").rrule == times.rrule


def test_no_event_lasts_longer_than_a_year_and_a_day() -> None:
    """R3a-1: one event lasts at most `MAX_DURATION` (366 days), all-day ones too."""
    assert MAX_DURATION == timedelta(days=366)
    assert check(_timed(366 * 24, None), "UTC").ends_at - AWARE.replace(hour=9) == MAX_DURATION
    assert _code(_timed(366 * 24 + 1 / 60, None)) == "event.too_long"
    first = date(2026, 1, 1)
    whole_year = Times(all_day=True, first_day=first, last_day=first + timedelta(days=365))
    assert check(whole_year, "UTC").recurs_until is not None
    longer = Times(all_day=True, first_day=first, last_day=first + timedelta(days=366))
    assert _code(longer) == "event.too_long"


def test_checking_a_series_for_overlaps_is_bounded() -> None:
    """The gap is looked for among the first `GAP_SAMPLE` occurrences (all of a counted
    series) and around every later RDATE: an endless daily series from 1900 with 500
    RDATEs in 2398 and 2399 is checked quickly."""
    start = datetime(1900, 1, 1, 9, tzinfo=UTC)
    far = tuple(datetime(2398, 1, 1, 12) + timedelta(days=n) for n in range(DATES_MAX))
    times = Times(
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        tzid="Europe/Berlin",
        rrule="FREQ=DAILY",
        rdates=far,
    )
    began = time.perf_counter()
    check(times, "UTC")
    assert time.perf_counter() - began < 2.0
