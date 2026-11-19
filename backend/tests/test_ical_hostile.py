"""Hostile files at the import limit (review M10 Task 7a, R7a-1 to R7a-4; re-check
RC7a-1 to RC7a-5): reading never raises and never hangs. Work is counted as Python
calls, as the review measured it (`sys.setprofile`), never timed (plan M10, Global
Constraints); where work is done inside C calls or Python loops without calls, a
structural cap bounds it (`test_ical_caps`), so the count stays faithful.

`HERD_TEST_ICAL_WALL=1` also times each shape (a loose check, off by default)."""

import os
import sys
import time
from types import FrameType

import pytest

from app.modules.calendars.ical import problems, reading
from tests.support import ical_hostile, ical_hostile_caps

SHAPES = {**ical_hostile.SHAPES, **ical_hostile_caps.SHAPES}
SIZE = ical_hostile.SIZE
# The most one file of `SIZE` may cost: reading 64,000 small events costs about 9
# million calls (the bytes alone), everything else is bound by `ical.budget` (2,000,000
# units of about two calls each).
MAX_CALLS = 15_000_000
MAX_SECONDS = 15  # loosely: about 3 s each on a developer machine


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


@pytest.mark.skipif(not os.environ.get("HERD_TEST_ICAL_WALL"), reason="timed: on request only")
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_a_hostile_file_at_the_size_limit_is_read_in_seconds(shape: str) -> None:
    data = SHAPES[shape](SIZE)
    began = time.process_time()
    reading.parse(data, default_zone="Europe/Berlin", limit=5000)
    assert time.process_time() - began < MAX_SECONDS
