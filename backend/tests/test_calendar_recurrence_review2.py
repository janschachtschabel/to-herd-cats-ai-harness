"""Review of M10 Task 2 (review-task-2.md): each test proves one finding."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.modules.calendars import recurrence
from app.modules.calendars.recurrence import RuleInvalid, Series

HOUR = timedelta(hours=1)


def _days(rule: str, start: datetime, until: datetime) -> list[date]:
    series = Series(start, HOUR, "UTC", False, rule)
    window = (start.replace(tzinfo=UTC) - HOUR, until.replace(tzinfo=UTC))
    return [o.recurrence_id.date() for o in recurrence.occurrences(series, *window)]


def test_byday_with_and_without_ordinals_is_a_union() -> None:
    # R2-1. RFC 5545 3.3.10: BYDAY is a list; "1MO,FR" of a month is its first Monday
    # and every Friday. Thursday 1 January 2026 is the start.
    found = _days("FREQ=MONTHLY;BYDAY=1MO,FR", datetime(2026, 1, 1, 9), datetime(2026, 2, 1))
    january = [date(2026, 1, day) for day in (1, 2, 5, 9, 16, 23, 30)]
    assert found == january


def test_yearly_byday_with_and_without_ordinals_is_a_union() -> None:
    # R2-1, yearly within a month: the second Monday of March and every Thursday of it.
    found = _days(
        "FREQ=YEARLY;BYMONTH=3;BYDAY=2MO,TH", datetime(2026, 3, 1, 9), datetime(2026, 4, 1)
    )
    assert found == [date(2026, 3, day) for day in (1, 5, 9, 12, 19, 26)]


@pytest.mark.parametrize(
    ("rule", "start", "expected"),
    [
        # The week's set is MO, WE, FR; its first is Monday 5 January, before the start
        # (Thursday 8): the first week gives the start alone, not Friday 9.
        ("FREQ=WEEKLY;BYDAY=MO,WE,FR;BYSETPOS=1", datetime(2026, 1, 8, 9), (8, 12, 19)),
        # The second of MO, WE, FR is Wednesday: the start (Wednesday 7), not Friday 9.
        ("FREQ=WEEKLY;BYDAY=MO,WE,FR;BYSETPOS=2", datetime(2026, 1, 7, 9), (7, 14, 21)),
    ],
)
def test_bysetpos_of_a_weekly_rule_counts_within_the_whole_first_week(
    rule: str, start: datetime, expected: tuple[int, ...]
) -> None:
    # R2-2. BYSETPOS selects from the period's set (the whole week from WKST), also in
    # the week DTSTART lies in; the weeks after it already do.
    found = _days(rule, start, datetime(2026, 1, 22))
    assert found == [date(2026, 1, day) for day in expected]


@pytest.mark.parametrize("until", ["00010101T000000Z", "09990101T000000Z", "00010101", "09991231"])
def test_the_canonical_form_of_an_early_until_can_be_read_again(until: str) -> None:
    # R2-3. What check_rule returns is what gets stored; it must parse (or the rule
    # must be refused in the first place).
    try:
        canonical = recurrence.check_rule(f"FREQ=DAILY;UNTIL={until}")
    except RuleInvalid:
        return
    assert recurrence.check_rule(canonical) == canonical


def test_an_until_in_year_one_leaves_the_start_alone() -> None:
    # R2-3. UNTIL before DTSTART: the start alone (or a refusal with a code), never an
    # OverflowError out of the zone arithmetic.
    start = datetime(2026, 1, 5, 9)
    window = (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC))
    try:
        series = Series(start, HOUR, "America/New_York", False, "FREQ=DAILY;UNTIL=00010101T000000Z")
    except RuleInvalid:
        return
    assert [o.recurrence_id for o in recurrence.occurrences(series, *window)] == [start]
    assert recurrence.last_end(series) == datetime(2026, 1, 5, 15, tzinfo=UTC)


@pytest.mark.parametrize(
    "rule", ["FREQ=DAILY;COUNT=²", "FREQ=DAILY;INTERVAL=①", "FREQ=DAILY;COUNT=1²"]
)
def test_digits_that_are_no_numbers_are_refused_with_a_code(rule: str) -> None:
    # R2-4. str.isdigit() is true for "²", int() refuses it: a bare ValueError without
    # `code` reaches the caller (a 500 in the API, an aborted import).
    with pytest.raises(RuleInvalid) as refused:
        recurrence.check_rule(rule)
    assert refused.value.code == "event.rrule_invalid"
