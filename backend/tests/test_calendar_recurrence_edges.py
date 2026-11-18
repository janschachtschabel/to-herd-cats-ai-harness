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


def _days(rule: str, start: datetime, until: datetime) -> list[datetime]:
    series = Series(start, HOUR, "UTC", False, rule)
    window = (start.replace(tzinfo=UTC), until.replace(tzinfo=UTC))
    return [o.recurrence_id for o in recurrence.occurrences(series, *window)]


def test_a_mixed_byday_of_a_year_without_bymonth_counts_within_the_year() -> None:
    # R2-1: "20MO,SU" of a year is its 20th Monday (18 May 2026) and every Sunday.
    found = _days("FREQ=YEARLY;BYDAY=20MO,SU", datetime(2026, 5, 1, 9), datetime(2026, 6, 1))
    assert [d.day for d in found] == [1, 3, 10, 17, 18, 24, 31]


def test_bysetpos_picks_from_the_union_of_a_mixed_byday() -> None:
    # R2-1 with BYSETPOS: the set of January 2026 under "-1MO,TH" is every Thursday and
    # the last Monday (1, 8, 15, 22, 26, 29); its second to last is the 26th.
    rule = "FREQ=MONTHLY;BYDAY=-1MO,TH;BYSETPOS=-2"
    found = _days(rule, datetime(2026, 1, 1, 9), datetime(2026, 3, 1))
    assert found == [datetime(2026, 1, 1, 9), datetime(2026, 1, 26, 9), datetime(2026, 2, 23, 9)]


def test_occurrences_on_one_instant_show_once_by_the_earlier_id() -> None:
    # M-2: Pacific/Apia skipped 30 December 2011; 09:00 of the 30th moves on by the gap
    # and lands where 09:00 of the 31st is. One occurrence, named by the earlier id.
    apia = Series(datetime(2011, 12, 28, 9), HOUR, "Pacific/Apia", False, "FREQ=DAILY")
    window = (datetime(2011, 12, 27, tzinfo=UTC), datetime(2012, 1, 2, tzinfo=UTC))
    found = recurrence.occurrences(apia, *window)
    assert len({o.start for o in found}) == len(found)
    shared = [o for o in found if o.start == datetime(2011, 12, 30, 19, tzinfo=UTC)]
    assert [o.recurrence_id for o in shared] == [datetime(2011, 12, 30, 9)]
    assert recurrence.next_after(apia, datetime(2011, 12, 30, tzinfo=UTC)) == shared[0]
    # An RDATE at 03:30 beside the rule's 02:30 on the day the clocks spring forward.
    berlin = Series(
        datetime(2026, 3, 28, 2, 30),
        HOUR,
        "Europe/Berlin",
        False,
        "FREQ=DAILY;COUNT=3",
        rdates=(datetime(2026, 3, 29, 3, 30),),
    )
    day = (datetime(2026, 3, 29, tzinfo=UTC), datetime(2026, 3, 30, tzinfo=UTC))
    assert [o.recurrence_id for o in recurrence.occurrences(berlin, *day)] == [
        datetime(2026, 3, 29, 2, 30)
    ]


def test_the_occurrence_at_an_instant_is_named_by_its_wall_time() -> None:
    # M-3: an occurrence in a gap keeps the wall time the rule names (02:30, RFC 5545
    # RECURRENCE-ID) while it starts at 03:30; recurrence_id_at finds it from the instant.
    berlin = Series(
        datetime(2026, 3, 27, 2, 30),
        HOUR,
        "Europe/Berlin",
        False,
        "FREQ=DAILY",
        exdates=(datetime(2026, 3, 30, 2, 30),),
    )
    at = recurrence.recurrence_id_at
    assert at(berlin, datetime(2026, 3, 29, 1, 30, tzinfo=UTC)) == datetime(2026, 3, 29, 2, 30)
    assert at(berlin, datetime(2026, 3, 28, 1, 30, tzinfo=UTC)) == datetime(2026, 3, 28, 2, 30)
    assert at(berlin, datetime(2026, 3, 30, 0, 30, tzinfo=UTC)) == datetime(2026, 3, 30, 2, 30)
    assert at(berlin, datetime(2026, 3, 29, 1, 31, tzinfo=UTC)) is None
    assert at(berlin, datetime(2026, 3, 26, 1, 30, tzinfo=UTC)) is None
    apia = Series(datetime(2011, 12, 28, 9), HOUR, "Pacific/Apia", False, "FREQ=DAILY")
    assert at(apia, datetime(2011, 12, 30, 19, tzinfo=UTC)) == datetime(2011, 12, 30, 9)
    with pytest.raises(ValueError):
        at(berlin, datetime(2026, 3, 29, 1, 30))


def test_aware_ids_are_read_as_wall_times_of_the_series() -> None:
    # M-5: an aware id is the series' wall time of that instant, not a TypeError.
    berlin = Series(datetime(2026, 1, 5, 9), HOUR, "Europe/Berlin", False, "FREQ=DAILY")
    assert recurrence.is_occurrence(berlin, datetime(2026, 1, 7, 8, tzinfo=UTC))
    assert not recurrence.is_occurrence(berlin, datetime(2026, 1, 7, 9, tzinfo=UTC))
    assert recurrence.count_before(berlin, datetime(2026, 1, 7, 8, tzinfo=UTC)) == 2
    whole = Series(datetime(2026, 1, 5), timedelta(days=1), None, True, "FREQ=WEEKLY")
    assert recurrence.is_occurrence(whole, datetime(2026, 1, 12, tzinfo=UTC))
    assert recurrence.count_before(whole, datetime(2026, 1, 19, tzinfo=UTC)) == 2


TIME_ENDS = [
    (datetime.min.replace(tzinfo=UTC), datetime(1, 1, 3, tzinfo=UTC)),
    (datetime(9999, 12, 30, tzinfo=UTC), datetime.max.replace(tzinfo=UTC)),
    (datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC)),
]


@pytest.mark.parametrize("tzid", ["Pacific/Kiritimati", "Pacific/Pago_Pago", None])
def test_windows_at_the_ends_of_time_answer(tzid: str | None) -> None:
    # M-4: windows and instants near datetime.min/max answer like any window beyond the
    # series, never with an OverflowError.
    duration = timedelta(days=1) if tzid is None else HOUR
    every = Series(
        datetime(2026, 1, 5, 0 if tzid is None else 9),
        duration,
        tzid,
        tzid is None,
        "FREQ=DAILY;COUNT=3",
    )
    for window, expected in zip(TIME_ENDS, (0, 0, 3), strict=True):
        assert len(recurrence.occurrences(every, *window)) == expected
    lowest, highest = TIME_ENDS[2]
    assert recurrence.next_after(every, highest) is None
    first = recurrence.next_after(every, lowest)
    assert first is not None and first.recurrence_id == every.start
    assert recurrence.recurrence_id_at(every, lowest) is None
    assert recurrence.recurrence_id_at(every, highest) is None
    endless = Series(every.start, duration, tzid, tzid is None, "FREQ=YEARLY")
    assert recurrence.next_after(endless, highest) is None
    assert recurrence.occurrences(endless, *TIME_ENDS[1]) == []
    with pytest.raises(ValueError):
        recurrence.occurrences(every, datetime(2026, 1, 1), datetime(2026, 2, 1))


def test_a_duration_must_end_within_the_calendars_years() -> None:
    # M-4: an end beyond 2399 would overflow on the way; it is refused like a start there.
    for duration in (timedelta.max, timedelta(days=400 * 366)):
        with pytest.raises(recurrence.SeriesInvalid) as refused:
            Series(datetime(2026, 1, 5, 9), duration, "Europe/Berlin", False, "FREQ=DAILY")
        assert refused.value.code == "event.time_out_of_range"
    longest = datetime(2400, 1, 1) - datetime(1900, 1, 1, 9)
    every = Series(
        datetime(1900, 1, 1, 9),
        longest,
        "Europe/Berlin",
        False,
        "FREQ=YEARLY;UNTIL=23991231T000000Z",
    )
    assert recurrence.last_end(every) is not None
    assert len(recurrence.occurrences(every, *TIME_ENDS[2])) == 500


@pytest.mark.parametrize("rule", ["FREQ=DAILY;", "FREQ=DAILY;COUNT=3; ", "rrule:freq=daily;"])
def test_a_trailing_semicolon_is_taken(rule: str) -> None:
    # M-7: some producers end a rule with ";"; an empty part elsewhere stays refused.
    assert recurrence.check_rule(rule).startswith("FREQ=DAILY")


@pytest.mark.parametrize("rule", ["FREQ=DAILY;;", "FREQ=DAILY;;COUNT=3", ";FREQ=DAILY", ";"])
def test_empty_parts_are_refused(rule: str) -> None:
    with pytest.raises(RuleInvalid) as refused:
        recurrence.check_rule(rule)
    assert refused.value.code == "event.rrule_invalid"
