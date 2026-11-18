"""Edges of recurrence found in the review of M10 Task 2 (review-task-2.md): digits,
the years of UNTIL, instants shared by two occurrences, gap occurrences, windows at the
ends of time, aware ids, a trailing semicolon."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.calendars import recurrence
from app.modules.calendars.recurrence import RuleInvalid, Series

HOUR = timedelta(hours=1)


@pytest.mark.parametrize(
    "rule",
    [
        "FREQ=YEARLY;BYMONTH=٣",  # Arabic-Indic three
        "FREQ=MONTHLY;BYDAY=١MO",
        "FREQ=MONTHLY;BYMONTHDAY=１",  # full-width one
        "FREQ=WEEKLY;BYDAY=MO;BYSETPOS=١",
        "FREQ=DAILY;UNTIL=٢٠٢٦0101",
        "FREQ=DAILY;UNTIL=20260101T٠٩0000Z",
        "FREQ=DAILY;COUNT=٣",
    ],
)
def test_only_ascii_digits_are_numbers(rule: str) -> None:
    # M-1: `\d` and `str.isdigit()` take any Unicode digit; RFC 5545 numbers are ASCII.
    with pytest.raises(RuleInvalid) as refused:
        recurrence.check_rule(rule)
    assert refused.value.code == "event.rrule_invalid"


@pytest.mark.parametrize(
    "until",
    [
        "00010101",
        "09991231T000000Z",
        "18991231",
        "18991231T235959Z",
        "24000101",
        "24000101T000000Z",
        "99991231T235959Z",
    ],
)
def test_an_until_outside_the_calendars_years_is_refused(until: str) -> None:
    # R2-3: series lie in 1900 to 2399; an UNTIL outside them is refused like a start
    # there, with a code, never an OverflowError later.
    with pytest.raises(RuleInvalid) as refused:
        recurrence.check_rule(f"FREQ=DAILY;UNTIL={until}")
    assert refused.value.code == "event.time_out_of_range"


@pytest.mark.parametrize(
    ("until", "tzid"),
    [
        ("19000101T000000Z", "America/New_York"),
        ("19000101T000000Z", "Pacific/Kiritimati"),
        ("23991231T235959Z", "Pacific/Kiritimati"),
        ("23991231T235959Z", "Pacific/Pago_Pago"),
        ("19000101", None),
        ("23991231", None),
    ],
)
def test_an_until_at_the_ends_of_the_years_reads_back_and_expands(
    until: str, tzid: str | None
) -> None:
    # R2-3: the canonical text is what gets stored; it must read back as itself, and
    # every helper must answer without an OverflowError in any zone.
    canonical = recurrence.check_rule(f"FREQ=DAILY;UNTIL={until}")
    assert canonical == f"FREQ=DAILY;UNTIL={until}"
    assert recurrence.check_rule(canonical) == canonical
    start = datetime(1900, 1, 1) if until.startswith("1900") else datetime(2399, 12, 30)
    series = Series(
        start, timedelta(days=1) if tzid is None else HOUR, tzid, tzid is None, canonical
    )
    recurrence.check_series(series)
    window = (datetime(1899, 12, 1, tzinfo=UTC), datetime(2400, 2, 1, tzinfo=UTC))
    assert recurrence.occurrences(series, *window)[0].recurrence_id == start
    assert recurrence.last_end(series) is not None
    assert recurrence.next_after(series, window[0]) is not None
