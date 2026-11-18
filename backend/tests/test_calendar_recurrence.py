"""Recurrence (plan M10 decision 6), pure: rules are checked, series expanded in the
wall time of their zone and localised afterwards; RDATE, EXDATE and RECURRENCE-ID are
wall times."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.calendars import recurrence
from app.modules.calendars.recurrence import Series

HOUR = timedelta(hours=1)
WIDE = (datetime(1990, 1, 1, tzinfo=UTC), datetime(2040, 1, 1, tzinfo=UTC))


def at(text: str) -> datetime:
    return datetime.fromisoformat(text)


def series(start: str, rule: str | None, tzid: str | None = "Europe/Berlin", **kw) -> Series:  # type: ignore[no-untyped-def]
    return Series(
        start=at(start),
        duration=kw.pop("duration", HOUR),
        tzid=tzid,
        all_day=kw.pop("all_day", False),
        rrule=rule,
        rdates=tuple(at(t) for t in kw.pop("rdates", ())),
        exdates=tuple(at(t) for t in kw.pop("exdates", ())),
    )


MATRIX = {
    "daily_over_spring_change": (
        series("2026-03-27T09:00", "FREQ=DAILY;COUNT=4"),
        [
            "2026-03-27T09:00+01:00",
            "2026-03-28T09:00+01:00",
            "2026-03-29T09:00+02:00",
            "2026-03-30T09:00+02:00",
        ],
    ),
    "daily_over_autumn_change": (
        series("2026-10-23T09:00", "FREQ=DAILY;COUNT=4"),
        [
            "2026-10-23T09:00+02:00",
            "2026-10-24T09:00+02:00",
            "2026-10-25T09:00+01:00",
            "2026-10-26T09:00+01:00",
        ],
    ),
    "in_the_gap_moves_on": (
        series("2026-03-28T02:30", "FREQ=DAILY;COUNT=3"),
        ["2026-03-28T02:30+01:00", "2026-03-29T03:30+02:00", "2026-03-30T02:30+02:00"],
    ),
    "doubled_takes_the_first": (
        series("2026-10-24T02:30", "FREQ=DAILY;COUNT=3"),
        ["2026-10-24T02:30+02:00", "2026-10-25T02:30+02:00", "2026-10-26T02:30+01:00"],
    ),
    "weekly_every_other_mo_we_fr_week_from_sunday": (
        series("2026-01-07T10:00", "FREQ=WEEKLY;BYDAY=MO,WE,FR;INTERVAL=2;WKST=SU;COUNT=5"),
        [
            "2026-01-07T10:00+01:00",
            "2026-01-09T10:00+01:00",
            "2026-01-19T10:00+01:00",
            "2026-01-21T10:00+01:00",
            "2026-01-23T10:00+01:00",
        ],
    ),
    # RFC 5545 3.8.5.3: the same rule gives other days with another week start
    "rfc_wkst_su": (
        series(
            "1997-08-05T09:00",
            "FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=SU",
            "America/New_York",
        ),
        [
            "1997-08-05T09:00-04:00",
            "1997-08-17T09:00-04:00",
            "1997-08-19T09:00-04:00",
            "1997-08-31T09:00-04:00",
        ],
    ),
    "rfc_wkst_mo": (
        series(
            "1997-08-05T09:00",
            "FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU;WKST=MO",
            "America/New_York",
        ),
        [
            "1997-08-05T09:00-04:00",
            "1997-08-10T09:00-04:00",
            "1997-08-19T09:00-04:00",
            "1997-08-24T09:00-04:00",
        ],
    ),
    "monthly_on_the_31st_skips_short_months": (
        series("2026-01-31T10:00", "FREQ=MONTHLY;BYMONTHDAY=31;COUNT=4"),
        [
            "2026-01-31T10:00+01:00",
            "2026-03-31T10:00+02:00",
            "2026-05-31T10:00+02:00",
            "2026-07-31T10:00+02:00",
        ],
    ),
    "last_friday": (
        series("2026-01-30T10:00", "FREQ=MONTHLY;BYDAY=-1FR;COUNT=3"),
        ["2026-01-30T10:00+01:00", "2026-02-27T10:00+01:00", "2026-03-27T10:00+01:00"],
    ),
    "last_working_day": (
        series("2026-01-30T10:00", "FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1;COUNT=4"),
        [
            "2026-01-30T10:00+01:00",
            "2026-02-27T10:00+01:00",
            "2026-03-31T10:00+02:00",
            "2026-04-30T10:00+02:00",
        ],
    ),
    "yearly_on_29_february": (
        series("2024-02-29T10:00", "FREQ=YEARLY;COUNT=3", "UTC"),
        ["2024-02-29T10:00+00:00", "2028-02-29T10:00+00:00", "2032-02-29T10:00+00:00"],
    ),
    "count": (
        series("2026-06-01T09:00", "FREQ=WEEKLY;COUNT=3"),
        ["2026-06-01T09:00+02:00", "2026-06-08T09:00+02:00", "2026-06-15T09:00+02:00"],
    ),
    # UNTIL is an instant: 26 October 09:00 CET is 08:00 UTC, the last (inclusive)
    "until_in_utc": (
        series("2026-10-23T09:00", "FREQ=DAILY;UNTIL=20261026T080000Z"),
        [
            "2026-10-23T09:00+02:00",
            "2026-10-24T09:00+02:00",
            "2026-10-25T09:00+01:00",
            "2026-10-26T09:00+01:00",
        ],
    ),
    "until_just_before": (
        series("2026-10-23T09:00", "FREQ=DAILY;UNTIL=20261026T075959Z"),
        ["2026-10-23T09:00+02:00", "2026-10-24T09:00+02:00", "2026-10-25T09:00+01:00"],
    ),
    "rdate_added_exdate_removed": (
        series(
            "2026-06-01T09:00",
            "FREQ=DAILY;COUNT=3",
            rdates=["2026-06-10T14:00"],
            exdates=["2026-06-02T09:00"],
        ),
        ["2026-06-01T09:00+02:00", "2026-06-03T09:00+02:00", "2026-06-10T14:00+02:00"],
    ),
    "all_day_over_a_month_change": (
        series(
            "2026-01-30T00:00", "FREQ=DAILY;COUNT=3", None, all_day=True, duration=timedelta(days=2)
        ),
        ["2026-01-30T00:00+00:00", "2026-01-31T00:00+00:00", "2026-02-01T00:00+00:00"],
    ),
}


@pytest.mark.parametrize("case", sorted(MATRIX))
def test_recurrence_matrix(case: str) -> None:
    given, expected = MATRIX[case]
    found = recurrence.occurrences(given, *WIDE)
    assert [o.start for o in found] == [at(text) for text in expected]
    assert all(o.end - o.start == given.duration for o in found)
    assert all(o.start.tzinfo is UTC for o in found)


def test_recurrence_ids_are_the_wall_times_the_rule_names() -> None:
    found = recurrence.occurrences(MATRIX["in_the_gap_moves_on"][0], *WIDE)
    assert [o.recurrence_id for o in found] == [
        datetime(2026, 3, 28, 2, 30),
        datetime(2026, 3, 29, 2, 30),  # 03:30 by the clock, 02:30 by the rule
        datetime(2026, 3, 30, 2, 30),
    ]


def test_the_window_holds_what_overlaps_it() -> None:
    daily = series("2026-06-01T09:00", "FREQ=DAILY", duration=2 * HOUR)
    # 2 June 09:00–11:00 CEST is 07:00–09:00 UTC
    found = recurrence.occurrences(
        daily, at("2026-06-02T08:00+00:00"), at("2026-06-02T09:00+00:00")
    )
    assert [o.recurrence_id for o in found] == [datetime(2026, 6, 2, 9)]
    assert (
        recurrence.occurrences(daily, at("2026-06-02T09:00+00:00"), at("2026-06-03T07:00+00:00"))
        == []
    )


def test_an_unsynchronised_start_is_the_first_occurrence() -> None:
    # RFC 5545 3.8.5.3: DTSTART always counts as the first occurrence, COUNT included
    monday = series("2026-06-01T09:00", "FREQ=WEEKLY;BYDAY=WE;COUNT=3")
    found = recurrence.occurrences(monday, *WIDE)
    assert [o.recurrence_id.day for o in found] == [1, 3, 10]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("FREQ=SECONDLY", "event.rrule_unsupported"),
        ("FREQ=MINUTELY;INTERVAL=15", "event.rrule_unsupported"),
        ("FREQ=HOURLY", "event.rrule_unsupported"),
        ("FREQ=DAILY;BYHOUR=9,17", "event.rrule_unsupported"),
        ("FREQ=YEARLY;BYWEEKNO=20", "event.rrule_unsupported"),
        ("FREQ=YEARLY;BYYEARDAY=100", "event.rrule_unsupported"),
        ("FREQ=DAILY;COUNT=5001", "event.rrule_unsupported"),
        ("FREQ=DAILY;UNTIL=20261231T090000", "event.rrule_unsupported"),  # floating
        ("", "event.rrule_invalid"),
        ("BYDAY=MO", "event.rrule_invalid"),
        ("FREQ=FORTNIGHTLY", "event.rrule_invalid"),
        ("FREQ=DAILY;FREQ=WEEKLY", "event.rrule_invalid"),
        ("FREQ=DAILY;COUNT=0", "event.rrule_invalid"),
        ("FREQ=DAILY;INTERVAL=0", "event.rrule_invalid"),
        ("FREQ=DAILY;COUNT=2;UNTIL=20260101", "event.rrule_invalid"),
        ("FREQ=DAILY;UNTIL=2026-01-01", "event.rrule_invalid"),
        ("FREQ=MONTHLY;BYMONTH=13", "event.rrule_invalid"),
        ("FREQ=MONTHLY;BYMONTHDAY=0", "event.rrule_invalid"),
        ("FREQ=WEEKLY;BYDAY=1MO", "event.rrule_invalid"),
        ("FREQ=MONTHLY;BYDAY=6MO", "event.rrule_invalid"),
        ("FREQ=MONTHLY;BYDAY=XX", "event.rrule_invalid"),
        ("FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=30,31", "event.rrule_invalid"),
        ("FREQ=MONTHLY;BYSETPOS=1", "event.rrule_invalid"),
        ("FREQ=WEEKLY;WKST=XY", "event.rrule_invalid"),
        ("FREQ=DAILY;X-NAME=1", "event.rrule_invalid"),
        ("FREQ", "event.rrule_invalid"),
        ("FREQ=DAILY;" + "BYMONTH=1;" * 60, "event.rrule_invalid"),
    ],
)
def test_rules_below_daily_and_broken_rules_are_refused(text: str, code: str) -> None:
    with pytest.raises(recurrence.RuleInvalid) as refused:
        recurrence.check_rule(text)
    assert refused.value.code == code


def test_check_rule_gives_the_canonical_form() -> None:
    assert recurrence.check_rule("rrule:freq=weekly;byday=fr,mo;interval=1;wkst=mo") == (
        "FREQ=WEEKLY;BYDAY=MO,FR"
    )
    assert recurrence.check_rule("FREQ=MONTHLY;BYDAY=-1FR;UNTIL=20261231") == (
        "FREQ=MONTHLY;UNTIL=20261231;BYDAY=-1FR"
    )
    assert (
        recurrence.check_rule(
            "WKST=SU;BYSETPOS=-1;BYDAY=FR,MO,TU,WE,TH;FREQ=MONTHLY;INTERVAL=2;UNTIL=20261231T230000Z"
        )
        == "FREQ=MONTHLY;UNTIL=20261231T230000Z;INTERVAL=2;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1;WKST=SU"
    )


def test_until_must_have_the_form_of_the_start() -> None:
    # a start with a zone takes UNTIL in UTC, an all-day start a date (RFC 5545 3.3.10)
    with pytest.raises(recurrence.RuleInvalid) as refused:
        series("2026-06-01T09:00", "FREQ=DAILY;UNTIL=20260610")
    assert refused.value.code == "event.rrule_invalid"
    with pytest.raises(recurrence.RuleInvalid):
        series(
            "2026-06-01T00:00",
            "FREQ=DAILY;UNTIL=20260610T000000Z",
            None,
            all_day=True,
            duration=timedelta(days=1),
        )


def test_a_series_checks_its_own_shape() -> None:
    cases = [
        (dict(start=datetime(2026, 6, 1, 9, tzinfo=UTC)), "event.invalid_time"),
        (dict(tzid=None), "event.invalid_time_zone"),
        (dict(tzid="Mars/Olympus"), "event.invalid_time_zone"),
        (dict(start=datetime(1899, 12, 31, 9)), "event.time_out_of_range"),
        (dict(start=datetime(2400, 1, 1, 9)), "event.time_out_of_range"),
        (dict(duration=-HOUR), "event.invalid_time"),
        (dict(all_day=True, tzid=None), "event.invalid_time"),  # 09:00 is no midnight
        (dict(rdates=(datetime(2026, 6, 2, 9, tzinfo=UTC),)), "event.invalid_time"),
        (dict(rrule="FREQ=HOURLY"), "event.rrule_unsupported"),
    ]
    for changes, code in cases:
        fields = dict(
            start=datetime(2026, 6, 1, 9),
            duration=HOUR,
            tzid="Europe/Berlin",
            all_day=False,
            rrule="FREQ=DAILY",
            rdates=(),
            exdates=(),
        )
        fields |= changes
        with pytest.raises(recurrence.SeriesInvalid) as refused:
            Series(**fields)  # type: ignore[arg-type]
        assert refused.value.code == code, changes


def test_check_series_refuses_a_rule_that_never_matches() -> None:
    # every seventh day from a Monday is a Monday: never a Tuesday
    never = series("2026-06-01T09:00", "FREQ=DAILY;INTERVAL=7;BYDAY=TU")
    with pytest.raises(recurrence.RuleInvalid) as refused:
        recurrence.check_series(never)
    assert refused.value.code == "event.rrule_invalid"
    recurrence.check_series(series("2026-06-01T09:00", "FREQ=DAILY;INTERVAL=7;BYDAY=MO"))
    recurrence.check_series(series("2026-06-01T09:00", None))


def test_too_many_occurrences_raise_too_dense() -> None:
    daily = series("2026-01-01T09:00", "FREQ=DAILY")
    start = at("2026-01-01T00:00+00:00")
    assert len(recurrence.occurrences(daily, start, start + timedelta(days=10), limit=10)) == 10
    with pytest.raises(recurrence.TooDense):
        recurrence.occurrences(daily, start, start + timedelta(days=11), limit=10)
    assert len(recurrence.occurrences(daily, start, start + timedelta(days=2000))) == 2000
    with pytest.raises(recurrence.TooDense) as refused:
        recurrence.occurrences(daily, start, start + timedelta(days=2001))
    assert refused.value.code == "calendar.window_too_dense"


def test_windows_beyond_the_horizon_are_empty() -> None:
    daily = series("2026-01-01T09:00", "FREQ=DAILY")
    assert (
        recurrence.occurrences(daily, at("2400-01-01T00:00+00:00"), at("2400-02-01T00:00+00:00"))
        == []
    )
    last = recurrence.occurrences(daily, at("2399-12-30T00:00+00:00"), at("2400-02-01T00:00+00:00"))
    assert [o.recurrence_id for o in last] == [datetime(2399, 12, 30, 9), datetime(2399, 12, 31, 9)]


def test_last_end_of_count_until_and_endless() -> None:
    counted = series("2026-06-01T09:00", "FREQ=DAILY;COUNT=3")
    assert recurrence.last_end(counted) == at("2026-06-03T10:00+02:00")
    until = series("2026-10-23T09:00", "FREQ=DAILY;UNTIL=20261026T080000Z")
    assert recurrence.last_end(until) == at("2026-10-26T10:00+01:00")
    assert recurrence.last_end(series("2026-06-01T09:00", "FREQ=DAILY")) is None
    single = series("2026-06-01T09:00", None, rdates=["2026-07-01T09:00"])
    assert recurrence.last_end(single) == at("2026-07-01T10:00+02:00")
    assert recurrence.last_end(series("2026-06-01T09:00", None)) == at("2026-06-01T10:00+02:00")
    # the last one deleted: the one before it ends the series
    deleted = series("2026-06-01T09:00", "FREQ=DAILY;COUNT=3", exdates=["2026-06-03T09:00"])
    assert recurrence.last_end(deleted) == at("2026-06-02T10:00+02:00")
    # more than the cap: as endless
    long = series("2026-06-01T09:00", "FREQ=DAILY;UNTIL=20410101T000000Z")
    assert recurrence.last_end(long) is None
    assert recurrence.last_end(long, cap=6000) == at("2040-12-31T10:00+01:00")


def test_next_after_skips_exdates() -> None:
    daily = series("2026-06-01T09:00", "FREQ=DAILY;COUNT=5", exdates=["2026-06-03T09:00"])
    nxt = recurrence.next_after(daily, at("2026-06-02T07:00+00:00"))  # 09:00 CEST itself
    assert nxt is not None
    assert nxt.start == at("2026-06-04T09:00+02:00")
    assert nxt.recurrence_id == datetime(2026, 6, 4, 9)
    assert recurrence.next_after(daily, at("2026-06-05T07:00+00:00")) is None
    endless = series("2026-06-01T09:00", "FREQ=YEARLY")
    far = recurrence.next_after(endless, at("2300-01-01T00:00+00:00"))
    assert far is not None and far.recurrence_id == datetime(2300, 6, 1, 9)


def test_count_before_counts_deleted_occurrences_too() -> None:
    counted = series(
        "2026-06-01T09:00",
        "FREQ=DAILY;COUNT=10",
        exdates=["2026-06-02T09:00"],
        rdates=["2026-05-01T09:00"],
    )
    assert recurrence.count_before(counted, datetime(2026, 6, 4, 9)) == 3
    assert recurrence.count_before(counted, datetime(2026, 6, 1, 9)) == 0


def test_is_occurrence_knows_the_rule_its_start_and_rdates() -> None:
    weekly = series(
        "2026-06-01T09:00",
        "FREQ=WEEKLY;BYDAY=MO,TH",
        rdates=["2026-06-03T14:00"],
        exdates=["2026-06-08T09:00"],
    )
    assert recurrence.is_occurrence(weekly, datetime(2026, 6, 1, 9))
    assert recurrence.is_occurrence(weekly, datetime(2026, 6, 4, 9))
    assert recurrence.is_occurrence(weekly, datetime(2026, 6, 3, 14))
    assert recurrence.is_occurrence(weekly, datetime(2026, 6, 8, 9))  # deleted, still the rule's
    assert recurrence.is_occurrence(weekly, datetime(2040, 6, 4, 9))
    assert not recurrence.is_occurrence(weekly, datetime(2026, 6, 2, 9))
    assert not recurrence.is_occurrence(weekly, datetime(2026, 6, 4, 10))


def test_exdates_match_as_wall_time_after_a_zone_rule_change() -> None:
    # the same series before and after its zone's offset changed: the deleted 09:00 stays
    # deleted, the moved 09:00 stays moved, though both are other instants now
    for tzid, offset in (("Etc/GMT-1", "+01:00"), ("Etc/GMT-2", "+02:00")):
        daily = series("2026-06-01T09:00", "FREQ=DAILY;COUNT=3", tzid, exdates=["2026-06-02T09:00"])
        found = recurrence.occurrences(daily, *WIDE)
        assert [o.start for o in found] == [
            at(f"2026-06-01T09:00{offset}"),
            at(f"2026-06-03T09:00{offset}"),
        ]
        assert recurrence.is_occurrence(daily, datetime(2026, 6, 3, 9))


def test_shift_moves_a_wall_time() -> None:
    assert recurrence.shift(datetime(2026, 3, 28, 9), timedelta(hours=1)) == datetime(
        2026, 3, 28, 10
    )
    with pytest.raises(ValueError, match="naive"):
        recurrence.shift(datetime(2026, 3, 28, 9, tzinfo=UTC), HOUR)
