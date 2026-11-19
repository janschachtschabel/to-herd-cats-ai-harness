"""An event's times as every write path checks them (`event_times.check`, review M10
task 3a, R3a-1 and R3a-3): aware instants in the calendar's years 1900 to 2399, each
problem 422 with its code and never a 500."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core.errors import ValidationFailed
from app.modules.calendars.event_times import Times, check

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
