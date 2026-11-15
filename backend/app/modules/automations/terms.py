"""The terms of an automation (plan M7 decision 5): pure functions, no database, no
clock of their own (the caller passes "now").

- A recurring automation has a cron expression (five fields, parsed by `cronsim`) in
  an IANA time zone. Its next term is the first instant after "now", never one
  computed from a missed term: after an outage it fires once, not once per term
  missed.
- Daylight saving time: a local time that does not exist that day (02:30 when the
  clocks jump from 02:00 to 03:00) falls to the next valid instant (03:00); a local
  time that exists twice (02:30 when they fall back) fires once, at the first of the
  two. Terms of every hour or every few minutes are real hours and minutes, so they
  fire in both of the doubled hours (they are an hour apart).
- Terms closer than 15 minutes are refused, checked on the next five terms
  (`check_recurring`, called when an automation is saved; its result is the preview).
"""

from datetime import UTC, datetime, timedelta, tzinfo
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

from cronsim import CronSim, CronSimError

MIN_SPACING = timedelta(minutes=15)
PREVIEW_TERMS = 5
MAX_CRON_CHARS = 120
# cronsim walks local wall times; around a fall back it may name an instant before
# "now" (the first of a doubled hour); a few steps always pass it.
_MAX_STEPS = 8


class TermError(ValueError):
    """A cron or a zone that cannot be used; `code` is the API's error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# Files of the system's zone directory that are no IANA zone of their own.
_NOT_ZONES = frozenset({"localtime", "posixrules"})


@lru_cache(maxsize=1)
def _zone_names() -> frozenset[str]:
    return frozenset(available_timezones()) - _NOT_ZONES


def zone(name: str) -> tzinfo:
    """The IANA zone `name` (`automation.invalid_time_zone` if it is none)."""
    if name not in _zone_names():
        raise TermError("automation.invalid_time_zone")
    return ZoneInfo(name)


def _terms(cron: str, where: tzinfo, after: datetime) -> CronSim:
    if not cron or len(cron) > MAX_CRON_CHARS or len(cron.split()) != 5:
        raise TermError("automation.invalid_cron")
    try:
        return CronSim(cron, after.astimezone(where))
    except CronSimError:
        raise TermError("automation.invalid_cron") from None


def next_term(cron: str, time_zone: str, now: datetime) -> datetime:
    """The first term of `cron` in `time_zone` after `now` (aware), in UTC."""
    if now.tzinfo is None:
        raise ValueError("now must carry its time zone")
    found = _terms(cron, zone(time_zone), now)
    for _ in range(_MAX_STEPS):
        try:
            term = next(found).astimezone(UTC)
        except (StopIteration, CronSimError):  # a date that never comes (31 February)
            break
        if term > now:
            return term
    raise TermError("automation.invalid_cron")


def upcoming(cron: str, time_zone: str, now: datetime, count: int) -> list[datetime]:
    """The next `count` terms after `now`, in UTC."""
    terms: list[datetime] = []
    at = now
    for _ in range(count):
        at = next_term(cron, time_zone, at)
        terms.append(at)
    return terms


def check_recurring(cron: str, time_zone: str, now: datetime) -> list[datetime]:
    """The next five terms, if no two of them are closer than 15 minutes
    (`automation.too_frequent`); refuses what is no cron or no zone."""
    preview = upcoming(cron, time_zone, now, PREVIEW_TERMS)
    if any(b - a < MIN_SPACING for a, b in zip(preview, preview[1:], strict=False)):
        raise TermError("automation.too_frequent")
    return preview
