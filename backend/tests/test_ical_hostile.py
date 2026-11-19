"""Hostile files at the import limit (review M10 Task 7a, R7a-1 to R7a-4): reading
never raises and never hangs. Work is counted as Python calls, as the review measured
it (`sys.setprofile`), never timed (plan M10, Global Constraints)."""

import sys
from types import FrameType

import pytest

from app.modules.calendars.ical import problems, reading
from tests.support.ical_hostile import SHAPES, SIZE

# The most one file of `SIZE` may cost: reading 64,000 small events costs about 9
# million calls (the bytes alone), everything else is bound by `ical.budget`.
MAX_CALLS = 15_000_000


def _counted(data: bytes) -> tuple[reading.Parsed, int]:
    count = 0

    def note(frame: FrameType, event: str, arg: object) -> None:
        nonlocal count
        if event == "call":
            count += 1

    sys.setprofile(note)
    try:
        parsed = reading.parse(data, default_zone="Europe/Berlin", limit=5000)
    finally:
        sys.setprofile(None)
    return parsed, count


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_a_hostile_file_at_the_size_limit_is_read_within_a_fixed_count_of_calls(
    shape: str,
) -> None:
    data = SHAPES[shape](SIZE)
    assert SIZE * 0.9 <= len(data) <= SIZE * 1.2
    parsed, calls = _counted(data)
    assert calls < MAX_CALLS, calls
    assert set(parsed.problems) <= problems.CODES
    assert len(parsed.events) + sum(parsed.problems.values()) >= 1
