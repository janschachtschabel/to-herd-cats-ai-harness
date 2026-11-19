"""The effective occurrences of stored events (`calendars/expansion.py`, review M10
task 3a, R3a-2 and R3a-11): one function for the window (3a), free/busy (5),
reminders (6) and feeds (8a); its work is bounded by counted operations, not by how
many series it is handed."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import inspect, true
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.pagination import PageParams
from app.core.principal import PrincipalType
from app.modules.calendars import expansion
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.event_repository import EventRepository
from app.modules.calendars.expansion import Budget, effective
from app.modules.calendars.window import list_window
from tests.factories import MakeUser
from tests.factories_calendar import actor_of, logged_in, new_calendar, new_event
from tests.factories_spaces import MakeSpace

WEEK = (datetime(2026, 11, 23, tzinfo=UTC), datetime(2026, 11, 30, tzinfo=UTC))
# Daily, but limited to months: its count per period may vary, so a counted one walks
# from its start on every read (no counted jump, `recurrence_count.per_block`).
WALKING_DAILY = "FREQ=DAILY;BYMONTH=1,2,3,4,5,6,7,8,9,10,11,12"


def _event(**fields: Any) -> CalendarEvent:
    start = fields.pop("starts_at", datetime(2026, 11, 2, 9, tzinfo=UTC))
    defaults: dict[str, Any] = {
        "id": uuid7(),
        "starts_at": start,
        "ends_at": start + timedelta(hours=1),
        "tzid": "Europe/Berlin",
        "all_day": False,
        "rrule": None,
        "rdates": [],
        "exdates": [],
        "organizer_type": PrincipalType.USER,
        "organizer_id": uuid.uuid4(),
    }
    return CalendarEvent(**{**defaults, **fields})


def test_effective_occurrences_skip_deleted_and_overridden_ones() -> None:
    """Rows in, effective occurrences out: a weekly series (Mondays 10:00 in Berlin)
    loses its EXDATE and the occurrence an override took; the override stands at its
    own time; an all-day event shows on its day in the viewer's zone only."""
    series = _event(rrule="FREQ=WEEKLY", exdates=[datetime(2026, 11, 30, 10)])
    moved = _event(
        starts_at=datetime(2026, 11, 24, 15, tzinfo=UTC),
        series_id=series.id,
        recurrence_id=datetime(2026, 11, 23, 10),
    )
    day = datetime(2026, 11, 29, tzinfo=UTC)
    sunday = _event(starts_at=day, ends_at=day + timedelta(days=1), tzid=None, all_day=True)
    taken = {(series.id, datetime(2026, 11, 23, 10))}
    week = (WEEK[0], WEEK[1] + timedelta(days=8))
    budget = Budget()
    found = effective([series, moved, sunday], taken, *week, viewer_zone="UTC", budget=budget)
    assert sorted((o.start, e.id) for o, e in found) == sorted(
        [
            (datetime(2026, 11, 24, 15, tzinfo=UTC), moved.id),
            (day, sunday.id),
            (datetime(2026, 12, 7, 9, tzinfo=UTC), series.id),
        ]
    )
    assert budget.spent() > 0
    far_east = effective([sunday], set(), *WEEK, viewer_zone="Pacific/Kiritimati", budget=Budget())
    assert [e.id for _, e in far_east] == [sunday.id]
    east_monday = (datetime(2026, 11, 29, 10, tzinfo=UTC), datetime(2026, 11, 30, 10, tzinfo=UTC))
    assert (
        effective([sunday], set(), *east_monday, viewer_zone="Pacific/Kiritimati", budget=Budget())
        == []
    )


def test_work_beyond_the_budget_is_too_dense() -> None:
    """A counted series whose count per period may vary runs from its start (a daily
    rule limited to months does not jump): its candidates up to the window count, and
    so does every row."""
    counted = _event(
        starts_at=datetime(2015, 1, 1, 9, tzinfo=UTC), rrule=f"{WALKING_DAILY};COUNT=5000"
    )
    spent = Budget()
    effective([counted], set(), *WEEK, viewer_zone="UTC", budget=spent)
    assert spent.spent() > 4000
    with pytest.raises(expansion.TooDense):
        effective([counted], set(), *WEEK, viewer_zone="UTC", budget=Budget(work=spent.spent() - 1))
    with pytest.raises(expansion.TooDense):
        effective([counted], set(), *WEEK, viewer_zone="UTC", budget=Budget(occurrences=6))


async def test_the_window_answers_too_dense_beyond_its_work_bound(
    monkeypatch: pytest.MonkeyPatch, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    calendar = await new_calendar(client, space.id, "Team")
    for _ in range(3):
        await new_event(
            client,
            calendar["id"],
            starts_at="2026-01-01T10:00:00+01:00",
            ends_at="2026-01-01T11:00:00+01:00",
            rrule=f"{WALKING_DAILY};COUNT=400",
        )
    params = {"from": "2026-11-23T00:00:00Z", "to": "2026-11-24T00:00:00Z"}
    assert len((await client.get("/api/calendar/events", params=params)).json()["items"]) == 3
    monkeypatch.setattr(expansion, "MAX_WORK", 3 * 300)  # 3 × ~330 candidates
    r = await client.get("/api/calendar/events", params=params)
    assert (r.status_code, r.json()["error"]["code"]) == (422, "calendar.window_too_dense")


async def test_the_window_loads_no_description(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """R3a-8: the window never shows a description (up to 20,000 characters), so its
    statement does not load it, and reading it from such a row raises instead of
    loading it row by row."""
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    calendar = await new_calendar(client, space.id, "Team")
    await new_event(client, calendar["id"], description="x" * 20_000)
    session.expunge_all()
    rows = await EventRepository(session, author.org_id).in_window(
        true(), true(), *WEEK, calendar_ids=None, title=None, full=true(), limit=10
    )
    [(event, _)] = rows
    assert "description" in inspect(event).unloaded
    with pytest.raises(InvalidRequestError):
        _ = event.description


async def test_the_window_spends_from_a_budget_its_caller_hands_over(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """A caller that measures (scripts/measure_calendar.py, plan M10 Task 3c) hands its
    own `Budget` in and reads the rows and candidates the call spent from it."""
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    calendar = await new_calendar(client, space.id, "Team")
    await new_event(client, calendar["id"], rrule="FREQ=WEEKLY")
    await new_event(client, calendar["id"])
    budget = Budget()
    page = await list_window(
        session,
        await actor_of(session, author),
        start=WEEK[0],
        end=WEEK[1],
        calendar_ids=None,
        space_id=None,
        mine=False,
        query=None,
        params=PageParams(limit=100),
        budget=budget,
    )
    assert len(page.items) == 2
    assert budget.rows == 2
    assert budget.counter.candidates >= 1
    assert budget.spent() == 2 * expansion.ROW_WORK + budget.counter.candidates
