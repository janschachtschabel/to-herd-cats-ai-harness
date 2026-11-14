"""The terms of an automation (plan M7 decision 5): cron in an IANA zone, the next
term from "now", daylight saving time in `Europe/Berlin`, the 15-minute rule on the
next five terms, and refusals for what is no cron or no zone."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.automations import terms
from app.modules.automations.terms import TermError

BERLIN = "Europe/Berlin"


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[misc]


def test_the_next_term_is_the_first_after_now_in_the_zone() -> None:
    # 08:00 in Berlin is 06:00 UTC in summer, 07:00 UTC in winter
    assert terms.next_term("0 8 * * *", BERLIN, utc(2026, 7, 1, 5, 0)) == utc(2026, 7, 1, 6, 0)
    assert terms.next_term("0 8 * * *", BERLIN, utc(2026, 7, 1, 6, 0)) == utc(2026, 7, 2, 6, 0)
    assert terms.next_term("0 8 * * *", BERLIN, utc(2026, 12, 1, 9, 0)) == utc(2026, 12, 2, 7, 0)


def test_a_time_that_does_not_exist_falls_to_the_next_valid_instant() -> None:
    # 29 March 2026: 02:00 CET jumps to 03:00 CEST; 02:30 does not exist that day
    first = terms.next_term("30 2 * * *", BERLIN, utc(2026, 3, 28, 12, 0))
    assert first == utc(2026, 3, 29, 1, 0)  # 03:00 CEST
    assert terms.next_term("30 2 * * *", BERLIN, first) == utc(2026, 3, 30, 0, 30)


def test_a_time_that_exists_twice_fires_once() -> None:
    # 25 October 2026: 03:00 CEST falls back to 02:00 CET; 02:30 happens twice
    first = terms.next_term("30 2 * * *", BERLIN, utc(2026, 10, 24, 12, 0))
    assert first == utc(2026, 10, 25, 0, 30)  # 02:30 CEST, the first of the two
    after = terms.next_term("30 2 * * *", BERLIN, first)
    assert after == utc(2026, 10, 26, 1, 30)  # not 02:30 CET the same night
    # a late firing inside the second hour (a catch-up) does not fire the second 02:30
    late = utc(2026, 10, 25, 1, 10)  # 02:10 CET
    assert terms.next_term("30 2 * * *", BERLIN, late) == utc(2026, 10, 26, 1, 30)


def test_an_hourly_term_keeps_its_hours_through_the_fall_back() -> None:
    # every hour is a real hour: 02:00 CEST and 02:00 CET are an hour apart
    got = terms.upcoming("0 * * * *", BERLIN, utc(2026, 10, 24, 23, 30), 4)
    assert got == [utc(2026, 10, 25, h, 0) for h in range(0, 4)]


def test_upcoming_lists_the_next_terms_in_order() -> None:
    got = terms.upcoming("0 9 * * 1-5", BERLIN, utc(2026, 11, 13, 10, 0), 3)  # a Friday
    assert got == [utc(2026, 11, 16, 8, 0), utc(2026, 11, 17, 8, 0), utc(2026, 11, 18, 8, 0)]


@pytest.mark.parametrize(
    "cron",
    ["*/15 * * * *", "0 * * * *", "0 9 * * *", "0,15,30,45 8-17 * * 1-5", "0 0 1 * *"],
)
def test_terms_at_least_15_minutes_apart_are_accepted(cron: str) -> None:
    preview = terms.check_recurring(cron, BERLIN, utc(2026, 11, 14, 12, 0))
    assert len(preview) == terms.PREVIEW_TERMS
    assert all(b - a >= timedelta(minutes=15) for a, b in zip(preview, preview[1:], strict=False))


@pytest.mark.parametrize("cron", ["* * * * *", "*/10 * * * *", "0,5 9 * * *", "0,14 * * * *"])
def test_terms_closer_than_15_minutes_are_refused(cron: str) -> None:
    with pytest.raises(TermError) as caught:
        terms.check_recurring(cron, BERLIN, utc(2026, 11, 14, 8, 0))
    assert caught.value.code == "automation.too_frequent"


def test_closeness_counts_only_the_next_five_terms() -> None:
    # 09:00 and 09:05 on the first of January: far beyond the next five terms (daily 12:00)
    late = "0 12 * * *"
    assert terms.check_recurring(late, BERLIN, utc(2026, 11, 14, 8, 0))
    with pytest.raises(TermError):  # but caught when they are among the next five
        terms.check_recurring("0,5 9 1 1 *", BERLIN, utc(2026, 12, 31, 12, 0))


@pytest.mark.parametrize("cron", ["", "61 * * * *", "* * *", "0 9 * * * *", "every day"])
def test_what_is_no_cron_is_refused(cron: str) -> None:
    with pytest.raises(TermError) as caught:
        terms.check_recurring(cron, BERLIN, utc(2026, 11, 14, 8, 0))
    assert caught.value.code == "automation.invalid_cron"


@pytest.mark.parametrize("zone", ["", "Mars/Olympus", "../etc/passwd", "localtime", "Berlin"])
def test_what_is_no_iana_zone_is_refused(zone: str) -> None:
    with pytest.raises(TermError) as caught:
        terms.check_recurring("0 9 * * *", zone, utc(2026, 11, 14, 8, 0))
    assert caught.value.code == "automation.invalid_time_zone"


def test_utc_is_a_zone() -> None:
    assert terms.next_term("0 9 * * *", "UTC", utc(2026, 11, 14, 8, 0)) == utc(2026, 11, 14, 9, 0)


def test_now_must_carry_its_zone() -> None:
    with pytest.raises(ValueError):
        terms.next_term("0 9 * * *", BERLIN, datetime(2026, 11, 14, 8, 0))  # noqa: DTZ001


def test_a_date_that_never_comes_is_refused() -> None:
    with pytest.raises(TermError) as caught:
        terms.check_recurring("0 9 31 2 *", BERLIN, utc(2026, 11, 14, 8, 0))
    assert caught.value.code == "automation.invalid_cron"
