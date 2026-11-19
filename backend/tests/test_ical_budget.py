"""One bound on the work of one file (review M10 Task 7a, R7a-1, R7a-4): counted, never
timed; beyond it the rest is counted as `ical.over_budget`."""

from collections import Counter
from datetime import datetime, timedelta

import pytest

from app.modules.calendars.ical import budget, reading
from app.modules.calendars.ical.drafts import MAX_OVERRIDES
from app.modules.calendars.recurrence_rule import parse_rule


def _calendar(*parts: str) -> bytes:
    return ("BEGIN:VCALENDAR\r\n" + "".join(parts) + "END:VCALENDAR\r\n").encode()


def _event(uid: str, body: str) -> str:
    return f"BEGIN:VEVENT\r\nUID:{uid}\r\n{body}\r\nEND:VEVENT\r\n"


def _parse(data: bytes) -> reading.Parsed:
    return reading.parse(data, default_zone="Europe/Berlin", limit=5000)


def test_beyond_the_budget_the_rest_is_counted_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = "DTSTART:20260105T100000Z\r\nRRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=10"
    data = _calendar(*(_event(f"e{n}", rule) for n in range(50)))
    each = budget.check_cost(
        parse_rule("FREQ=WEEKLY;BYDAY=MO;COUNT=10"), datetime(2026, 1, 5), datetime(2026, 1, 5)
    )
    monkeypatch.setattr(budget, "WORK_LIMIT", 20 * each)
    first = _parse(data)
    assert 0 < len(first.events) < 50
    assert first.problems == Counter({"ical.over_budget": 50 - len(first.events)})
    assert _parse(data) == first  # counted, not timed: the same file gets as far


def test_a_series_takes_at_most_max_overrides() -> None:
    first = datetime(2026, 1, 1, 10)

    def stamp(moment: datetime) -> str:
        return moment.strftime("%Y%m%dT%H%M%SZ")

    series = _event("s", f"DTSTART:{stamp(first)}\r\nRRULE:FREQ=DAILY;COUNT=2000")
    overrides = [
        _event(
            "s",
            f"RECURRENCE-ID:{stamp(first + timedelta(days=d))}\r\nDTSTART:{stamp(first + timedelta(days=d, hours=1))}",
        )
        for d in range(MAX_OVERRIDES + 5)
    ]
    parsed = _parse(_calendar(series, *overrides))
    assert len(parsed.events[0].overrides) == MAX_OVERRIDES
    assert parsed.problems == Counter({"ical.over_limit": 5})
