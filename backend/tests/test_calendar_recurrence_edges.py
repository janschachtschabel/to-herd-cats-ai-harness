"""Edges of recurrence found in the review of M10 Task 2 (review-task-2.md): digits,
the years of UNTIL, instants shared by two occurrences, gap occurrences, windows at the
ends of time, aware ids, a trailing semicolon."""

import pytest

from app.modules.calendars import recurrence
from app.modules.calendars.recurrence import RuleInvalid


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
