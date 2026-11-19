"""Many recurrence ids at once (`recurrence_ids`) answer what the single-value functions
answer for each (review M10 Task 7a, R7a-4, R7a-6)."""

import random
import sys
from datetime import UTC, datetime, timedelta
from types import FrameType

import pytest

from app.modules.calendars import recurrence, recurrence_ids
from app.modules.calendars.recurrence import Series

RULES = [
    None,
    "FREQ=DAILY;COUNT=40",
    "FREQ=DAILY;INTERVAL=3",
    "FREQ=WEEKLY;BYDAY=MO,TH;UNTIL=20290101T000000Z",
    "FREQ=MONTHLY;BYDAY=-1FR",
    "FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU;COUNT=12",
    # counted rules matched first without their COUNT (re-check RC7a-2)
    "FREQ=MONTHLY;BYDAY=MO,TU;BYSETPOS=-1;COUNT=7",
    "FREQ=DAILY;BYMONTH=2;BYMONTHDAY=29;COUNT=3",
    "FREQ=WEEKLY;INTERVAL=2;BYDAY=SU,WE;COUNT=9",
]


def _series(rule: str | None, rng: random.Random) -> Series:
    start = datetime(2026, 3, 1, 2, 30) + timedelta(days=rng.randrange(60))
    rdates = tuple(sorted({start + timedelta(days=rng.randrange(1, 900)) for _ in range(3)}))
    return Series(
        start=start,
        duration=timedelta(hours=1),
        tzid="Europe/Berlin",
        all_day=False,
        rrule=rule,
        rdates=rdates,
        exdates=rdates[:1],
    )


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("rule", RULES)
def test_many_ids_at_once_answer_as_one_at_a_time(rule: str | None, seed: int) -> None:
    rng = random.Random(seed)
    series = _series(rule, rng)
    near = [
        o.recurrence_id
        for o in recurrence.occurrences(
            series, datetime(2026, 1, 1, tzinfo=UTC), datetime(2031, 1, 1, tzinfo=UTC)
        )
    ]
    walls = rng.sample(near, min(8, len(near))) + [
        series.start + timedelta(days=rng.randrange(2000), hours=rng.randrange(24))
        for _ in range(8)
    ]
    spent: list[int] = []
    named = recurrence_ids.named(series, walls, spent.append)
    assert named == {w for w in walls if recurrence.is_occurrence(series, w)}
    assert sum(spent) > 0
    instants = [datetime(2026, 3, 29, 1, 30, tzinfo=UTC)] + [
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=30 * rng.randrange(100_000))
        for _ in range(20)
    ]
    at = recurrence_ids.ids_at(series, instants, spent.append)
    expected = {m: recurrence.recurrence_id_at(series, m) for m in instants}
    assert at == {m: rid for m, rid in expected.items() if rid is not None}


def test_spend_can_stop_the_work() -> None:
    series = Series(
        start=datetime(2026, 1, 1, 10),
        duration=timedelta(hours=1),
        tzid="Europe/Berlin",
        all_day=False,
        rrule="FREQ=DAILY;COUNT=5000",
    )

    class Stop(Exception):
        pass

    def spend(units: int) -> None:
        raise Stop

    with pytest.raises(Stop):
        recurrence_ids.named(series, [datetime(2039, 1, 1, 10)], spend)


def _sparse(count: str = ";COUNT=5000") -> Series:
    """A rule that matches every 28 years: 29 February on a Monday."""
    return Series(
        start=datetime(1904, 2, 29, 10),
        duration=timedelta(hours=1),
        tzid="UTC",
        all_day=False,
        rrule=f"FREQ=DAILY;BYMONTH=2;BYMONTHDAY=29;BYDAY=MO{count}",
    )


def test_a_counted_rule_is_scanned_from_its_start_only_for_values_it_may_name() -> None:
    """Re-check RC7a-2: a value the rule cannot name, far from the start, costs a pass
    over its own cluster, not one from the start (500 years of days: 640,000 calls)."""
    calls = 0

    def note(frame: FrameType, event: str, arg: object) -> None:
        nonlocal calls
        calls += event == "call"

    sys.setprofile(note)
    try:
        named = recurrence_ids.named(_sparse(), [datetime(2399, 1, 1, 10)], lambda units: None)
    finally:
        sys.setprofile(None)
    assert named == set()
    assert calls < 5_000


def test_a_pass_is_charged_for_every_period_it_scans() -> None:
    """Re-check RC7a-2: the days between two matches are scanned one by one; the charge
    follows the scan, not the matches found."""
    last = datetime(2388, 2, 29, 10)  # a Monday: the rule's 19th match
    assert last.weekday() == 0
    spent: list[int] = []
    assert recurrence_ids.named(_sparse(), [last], spent.append) == {last}
    days = (last - datetime(1904, 2, 29, 10)).days
    assert sum(spent) >= days
    # no match after 2388: the scan past the value runs to the horizon, and is charged
    spent.clear()
    assert recurrence_ids.named(_sparse(""), [datetime(2390, 1, 1, 10)], spent.append) == set()
    assert sum(spent) >= (datetime(2399, 12, 31) - datetime(2390, 1, 1)).days
