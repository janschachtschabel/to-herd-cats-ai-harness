"""The window's later pages (plan M10 Task 3c, remedy a): a page after a cursor needs
only the occurrences that start at or after the cursor's start, because pages run by
(start, event id). So a later page loads and expands from there, not the whole window
again, and still answers exactly what reading the whole window at once answers."""

import random
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailed
from app.core.pagination import PageParams
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.expansion import Budget
from app.modules.calendars.models import Calendar
from app.modules.calendars.window import list_window
from scripts.measure_calendar_events import series_rows, single_row
from tests.factories import MakeUser
from tests.factories_calendar import actor_of, logged_in, new_calendar, new_event, window
from tests.factories_spaces import MakeSpace

WEEKS = ("2026-11-09T00:00:00Z", "2026-12-07T00:00:00Z")


async def _page(
    session: AsyncSession, actor: Any, start: datetime, end: datetime, cursor: str | None
) -> tuple[Any, Budget]:
    budget = Budget()
    page = await list_window(
        session,
        actor,
        start=start,
        end=end,
        calendar_ids=None,
        space_id=None,
        mine=False,
        query=None,
        params=PageParams(limit=10, cursor=cursor),
        budget=budget,
    )
    return page, budget


async def test_a_later_page_expands_only_from_its_cursor(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """A daily series and one event a day over 30 days: the third page starts about
    20 days in, so it loads none of the single events before its cursor and expands
    the series from there."""
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    calendar = await new_calendar(client, space.id, "Team")
    await new_event(
        client,
        calendar["id"],
        starts_at="2026-11-01T08:00:00+01:00",
        ends_at="2026-11-01T08:30:00+01:00",
        rrule="FREQ=DAILY",
    )
    first = datetime(2026, 11, 1, 14, tzinfo=UTC)
    for day in range(30):
        moment = first + timedelta(days=day)
        await new_event(
            client,
            calendar["id"],
            starts_at=moment.isoformat(),
            ends_at=(moment + timedelta(hours=1)).isoformat(),
        )
    actor = await actor_of(session, author)
    start, end = first - timedelta(hours=14), first + timedelta(days=30)
    page, opening = await _page(session, actor, start, end, None)
    for _ in range(3):
        later_page, later = await _page(session, actor, start, end, page.next_cursor)
        page = later_page
    assert page.items[0].start >= start + timedelta(days=15)
    assert opening.rows == 31
    assert later.rows < opening.rows * 2 // 3
    assert later.counter.candidates < opening.counter.candidates * 2 // 3


@pytest.mark.parametrize("zone", ["UTC", "Pacific/Kiritimati", "Pacific/Pago_Pago"])
async def test_pages_answer_what_the_whole_window_answers(
    zone: str,
    session: AsyncSession,
    make_client: Any,
    make_user: MakeUser,
    make_space: MakeSpace,
) -> None:
    """Seeded: series of every kind (with EXDATEs and moved occurrences), single and
    all-day events, read in pages of 3 by viewers in UTC, UTC+14 and UTC−11, give the
    same occurrences in the same order as one page of 100."""
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    made = await new_calendar(client, space.id, "Team")
    calendar = await session.get_one(Calendar, made["id"])
    rng = random.Random(3)  # noqa: S311 - test data
    rows: list[dict[str, Any]] = []
    while len(rows) < 25:
        try:
            rows += series_rows(rng, author.org_id, calendar, author.id)
        except ValidationFailed:
            continue  # a draw the API refuses is drawn again
    rows += [single_row(rng, author.org_id, calendar, author.id) for _ in range(400)]
    masters = [
        {"series_id": None, "recurrence_id": None, **r} for r in rows if "series_id" not in r
    ]
    await session.execute(insert(CalendarEvent), masters)
    overrides = [r for r in rows if "series_id" in r]
    if overrides:
        await session.execute(insert(CalendarEvent), overrides)
    whole = await window(client, *WEEKS, limit=100, time_zone=zone)
    paged = await window(client, *WEEKS, limit=3, time_zone=zone)
    assert 30 < len(whole) < 100  # one page: the whole window at once
    assert [(i["start"], i["event_id"]) for i in paged] == [
        (i["start"], i["event_id"]) for i in whole
    ]
