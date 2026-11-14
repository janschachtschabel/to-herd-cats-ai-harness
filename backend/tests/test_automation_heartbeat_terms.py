"""Terms of a heartbeat (plan M7 decisions 5 and 7): every `interval` minutes inside
its active hours (weekdays and a local from–until in an IANA zone; a window may pass
midnight, and from = until is the whole day); after the window closes the next term
is the next opening. Pure functions, no database."""

from datetime import UTC, datetime, time, timedelta

import pytest

from app.modules.automations.heartbeat_terms import Hours, inside, next_heartbeat
from app.modules.automations.terms import TermError

MON, TUE, WED, THU, FRI, SAT, SUN = range(1, 8)
OFFICE = Hours(frozenset({MON, TUE, WED, THU, FRI}), time(9), time(17), "Europe/Berlin")


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_inside_the_window_the_next_term_is_one_interval_on() -> None:
    now = utc(2026, 11, 16, 9, 0)  # Monday 10:00 in Berlin
    assert next_heartbeat(30, OFFICE, now) == utc(2026, 11, 16, 9, 30)


def test_past_the_window_close_the_next_term_is_the_next_opening() -> None:
    now = utc(2026, 11, 16, 15, 45)  # Monday 16:45 in Berlin: 17:15 is past 17:00
    assert next_heartbeat(30, OFFICE, now) == utc(2026, 11, 17, 8, 0)  # Tuesday 09:00


def test_friday_evening_waits_for_monday() -> None:
    now = utc(2026, 11, 20, 15, 50)  # Friday 16:50
    assert next_heartbeat(60, OFFICE, now) == utc(2026, 11, 23, 8, 0)  # Monday 09:00


def test_outside_the_window_the_next_term_is_the_next_opening() -> None:
    assert next_heartbeat(15, OFFICE, utc(2026, 11, 16, 5, 0)) == utc(2026, 11, 16, 8, 0)
    assert next_heartbeat(15, OFFICE, utc(2026, 11, 21, 12, 0)) == utc(2026, 11, 23, 8, 0)


def test_a_window_over_midnight_belongs_to_the_day_it_opens() -> None:
    night = Hours(frozenset({FRI}), time(22), time(6), "Europe/Berlin")
    assert inside(night, utc(2026, 11, 20, 21, 30))  # Friday 22:30
    assert inside(night, utc(2026, 11, 21, 4, 59))  # Saturday 05:59, Friday's window
    assert not inside(night, utc(2026, 11, 21, 5, 0))  # Saturday 06:00: closed
    assert not inside(night, utc(2026, 11, 21, 21, 30))  # Saturday 22:30: not a Friday
    assert not inside(night, utc(2026, 11, 20, 4, 0))  # Friday 05:00: Thursday's night
    # Friday 23:00 + 2 h is Saturday 01:00, still Friday's window
    assert next_heartbeat(120, night, utc(2026, 11, 20, 22, 0)) == utc(2026, 11, 21, 0, 0)
    # Saturday 05:00 + 2 h passes 06:00: the next opening is next Friday 22:00
    assert next_heartbeat(120, night, utc(2026, 11, 21, 4, 0)) == utc(2026, 11, 27, 21, 0)


def test_from_equal_to_until_is_the_whole_day_and_days_join() -> None:
    days = Hours(frozenset({SAT, SUN}), time(0), time(0), "UTC")
    assert inside(days, utc(2026, 11, 21, 0, 0)) and inside(days, utc(2026, 11, 22, 23, 59))
    assert not inside(days, utc(2026, 11, 23, 0, 0))
    # Saturday 23:30 + 1 h runs on into Sunday without waiting for an opening
    assert next_heartbeat(60, days, utc(2026, 11, 21, 23, 30)) == utc(2026, 11, 22, 0, 30)


def test_weekdays_are_those_of_the_zone() -> None:
    """Monday 08:00–09:00 in Auckland is Sunday evening in UTC."""
    auckland = Hours(frozenset({MON}), time(8), time(9), "Pacific/Auckland")
    sunday_utc = utc(2026, 11, 22, 18, 0)  # Monday 07:00 NZDT (UTC+13)
    assert next_heartbeat(15, auckland, sunday_utc) == utc(2026, 11, 22, 19, 0)
    assert inside(auckland, utc(2026, 11, 22, 19, 30))
    assert not inside(auckland, utc(2026, 11, 23, 19, 30))  # Tuesday there


def test_an_opening_that_does_not_exist_falls_to_the_next_valid_instant() -> None:
    """28 March 2027 in Berlin: 02:00 jumps to 03:00; a window from 02:30 opens 03:00."""
    early = Hours(frozenset({SUN}), time(2, 30), time(5), "Europe/Berlin")
    saturday = utc(2027, 3, 27, 12, 0)
    assert next_heartbeat(30, early, saturday) == utc(2027, 3, 28, 1, 0)  # 03:00 CEST


def test_a_window_through_the_doubled_hour_lasts_its_real_hours() -> None:
    """25 October 2026 in Berlin: 03:00 falls back to 02:00; 01:00–03:00 lasts 3 h."""
    night = Hours(frozenset({SUN}), time(1), time(3), "Europe/Berlin")
    at = utc(2026, 10, 24, 23, 0)  # 01:00 CEST, the opening
    terms = []
    while at < utc(2026, 10, 25, 12, 0):  # this night's terms
        assert inside(night, at)
        terms.append(at)
        at = next_heartbeat(60, night, at)
    assert terms == [utc(2026, 10, 24, 23), utc(2026, 10, 25, 0), utc(2026, 10, 25, 1)]
    assert at == utc(2026, 11, 1, 0, 0)  # the next Sunday 01:00 CET


def test_hours_are_checked() -> None:
    with pytest.raises(TermError) as bad_zone:
        next_heartbeat(30, Hours(frozenset({MON}), time(9), time(17), "Mars/Base"), utc(2026, 1, 1))
    assert bad_zone.value.code == "automation.invalid_time_zone"
    for days in (frozenset(), frozenset({0}), frozenset({8})):
        with pytest.raises(TermError) as bad_days:
            next_heartbeat(30, Hours(days, time(9), time(17), "UTC"), utc(2026, 1, 1))
        assert bad_days.value.code == "automation.invalid_hours"
    for minutes, code in ((14, "automation.too_frequent"), (1441, "automation.invalid_interval")):
        with pytest.raises(TermError) as bad_interval:
            next_heartbeat(minutes, OFFICE, utc(2026, 1, 1))
        assert bad_interval.value.code == code
    with pytest.raises(ValueError):
        next_heartbeat(30, OFFICE, datetime(2026, 1, 1))  # noqa: DTZ001 -- naive on purpose


def test_terms_within_a_long_window_are_an_interval_apart() -> None:
    at, seen = utc(2026, 11, 16, 8, 0), []
    for _ in range(20):
        at = next_heartbeat(45, OFFICE, at)
        seen.append(at)
    for a, b in zip(seen, seen[1:], strict=False):
        assert b - a == timedelta(minutes=45) or b.time() == time(8, 0)
        assert inside(OFFICE, b)


def test_terms_are_never_closer_than_the_interval_across_a_window_edge() -> None:
    """Active 09:00–08:59 every day, every 15 minutes: the beat at 08:58 is followed
    at 09:13, not at the opening two minutes later (review M7, finding 13)."""
    nearly_whole_day = Hours(frozenset(range(1, 8)), time(9), time(8, 59), "Europe/Berlin")
    now = utc(2026, 11, 17, 7, 58)  # Tuesday 08:58 in Berlin, inside Monday's window
    assert next_heartbeat(15, nearly_whole_day, now) == utc(2026, 11, 17, 8, 13)


@pytest.mark.parametrize(
    ("start", "end"),
    [(time(9), time(8, 59)), (time(9), time(9, 10)), (time(22), time(6)), (time(9), time(17))],
)
def test_a_week_of_terms_keeps_the_interval(start: time, end: time) -> None:
    interval = 25  # not a divisor of the window: its last beat falls near the edge
    hours = Hours(frozenset({MON, TUE, WED, FRI, SAT}), start, end, "Europe/Berlin")
    at, terms = utc(2026, 11, 16, 0, 0), []
    while at < utc(2026, 11, 23, 0, 0):
        at = next_heartbeat(interval, hours, at)
        terms.append(at)
    gaps = [b - a for a, b in zip(terms, terms[1:], strict=False)]
    assert min(gaps) >= timedelta(minutes=interval)
    assert all(inside(hours, t) for t in terms)
