"""Review of M10 task 3a (`.superpowers/sdd/m10/review-task-3a.md`): one proving test
per important finding. Each fails on `8a2c448`."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.principal import SystemRole
from app.modules.audit.models import AuditLog
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.window import MAX_CANDIDATES
from tests.factories import MakeUser
from tests.factories_calendar import logged_in, new_calendar, new_event
from tests.factories_spaces import MakeSpace

WEEK = {"from": "2026-11-23T00:00:00Z", "to": "2026-11-30T00:00:00Z"}


async def _calendar(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> tuple[AsyncClient, dict[str, Any]]:
    author = await make_user()
    space = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    return client, await new_calendar(client, space.id, "Team")


async def test_one_long_series_does_not_close_the_window_for_everyone(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """R3a-1: a daily series whose every occurrence lasts six years overlaps itself
    2,191 times at any instant. One such (private) event of one author makes every
    window that touches the calendar 422 `calendar.window_too_dense` for every reader,
    however short the window. Either the series is refused, or the window stays
    readable."""
    author, reader = await make_user(), await make_user()
    space = await make_space("team", members=[(author, "editor"), (reader, "viewer")])
    moderator = await logged_in(make_client, await make_user(SystemRole.ADMIN))
    calendar = await new_calendar(moderator, space.id, "Team")
    client = await logged_in(make_client, author)
    await new_event(client, calendar["id"], title="Montagsrunde")
    r = await client.post(
        f"/api/calendars/{calendar['id']}/events",
        json={
            "title": "x",
            "starts_at": "2015-01-01T09:00:00+01:00",
            "ends_at": "2021-01-01T09:00:00+01:00",
            "rrule": "FREQ=DAILY",
            "visibility": "private",
        },
    )
    if r.status_code == 422:
        return  # refused when written: nothing to close the window with
    assert r.status_code == 201, r.text
    seen = await (await logged_in(make_client, reader)).get(
        "/api/calendar/events",
        params={"from": "2026-11-23T09:00:00Z", "to": "2026-11-23T09:00:01Z"},
    )
    assert seen.status_code == 200, seen.text


async def test_endless_series_that_do_not_occur_leave_the_window_readable(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """R3a-2: birthdays (yearly, endless, all in March). `MAX_CANDIDATES` counts every
    endless series that began before the window's end, whether or not it occurs in it:
    with 4,001 of them a week in November is 422 `calendar.window_too_dense` instead
    of empty, and stays so for good (an import takes 5,000 events, decision 10)."""
    client, calendar = await _calendar(make_client, make_user, make_space)
    made = await new_event(
        client,
        calendar["id"],
        all_day=True,
        first_day="2020-03-01",
        last_day="2020-03-01",
        starts_at=None,
        ends_at=None,
        tzid=None,
        rrule="FREQ=YEARLY",
    )
    row = (
        await session.execute(
            select(CalendarEvent).where(CalendarEvent.id == uuid.UUID(made["id"]))
        )
    ).scalar_one()
    template = {c.name: getattr(row, c.name) for c in CalendarEvent.__table__.columns}
    rows = []
    for n in range(MAX_CANDIDATES):
        day = datetime(2020, 3, 1, tzinfo=UTC) + timedelta(days=n % 28)
        rows.append(
            {
                **template,
                "id": uuid7(),
                "uid": f"birthday-{n}",
                "starts_at": day,
                "ends_at": day + timedelta(days=1),
            }
        )
    await session.execute(insert(CalendarEvent), rows)
    r = await client.get("/api/calendar/events", params=WEEK)
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []


async def test_times_the_api_cannot_read_answer_422_never_500(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """R3a-3: `starts_at`/`ends_at` are plain `datetime`s in `EventCreate`; a bound
    without an offset is compared with the other (TypeError), and an end near year
    9999 with a negative offset leaves `datetime` when brought to UTC (OverflowError):
    500 `internal` each. (Fix wave: the API takes aware instants only, so a bound
    without an offset is the request's 422 `validation_failed`; the service's own
    answer, `event.invalid_time`, is held in `test_events.py`.)"""
    client, calendar = await _calendar(make_client, make_user, make_space)
    url = f"/api/calendars/{calendar['id']}/events"
    cases = {
        "end without offset": ("2026-11-23T10:00:00+01:00", "2026-11-23T11:00:00"),
        "start without offset": ("2026-11-23T10:00:00", "2026-11-23T11:00:00+01:00"),
        "end beyond datetime": ("2026-11-23T10:00:00+01:00", "9999-12-31T23:59:59-10:00"),
    }
    got = {}
    for name, (starts_at, ends_at) in cases.items():
        r = await client.post(url, json={"title": "X", "starts_at": starts_at, "ends_at": ends_at})
        got[name] = (r.status_code, r.json()["error"]["code"])
    assert got == {
        "end without offset": (422, "validation_failed"),
        "start without offset": (422, "validation_failed"),
        "end beyond datetime": (422, "event.time_out_of_range"),
    }


async def test_reading_a_private_event_by_admin_power_leaves_a_trace_for_a_member_too(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """R3a-4 (the ruling "reading by id is the named way"): an admin who is a member
    of the team sees a colleague's private event only as busy in her window, and its
    whole content by clicking it (`GET /api/events/{id}`) or by adding `space_id=`.
    `access.require` audits only spaces she is not in, so this use of admin power
    (decision 3: "nur auf diesem Weg", the way that "steht im Audit") leaves no trace
    at all. Either she gets busy like every other member, or the read is audited."""
    author, admin_user = await make_user(), await make_user(SystemRole.ADMIN)
    team = await make_space("team", members=[(author, "moderator"), (admin_user, "viewer")])
    client = await logged_in(make_client, author)
    made = await new_event(
        client, (await new_calendar(client, team.id))["id"], title="Kur", visibility="private"
    )
    admin = await logged_in(make_client, admin_user)
    by_id = await admin.get(f"/api/events/{made['id']}")
    named = await admin.get("/api/calendar/events", params={**WEEK, "space_id": str(team.id)})
    assert (by_id.status_code, named.status_code) == (200, 200)
    read = [not by_id.json()["redacted"], *(not o["redacted"] for o in named.json()["items"])]
    if not any(read):
        return  # busy only: admin power was not used
    entries = (
        await session.scalars(select(AuditLog).where(AuditLog.actor_id == admin_user.id))
    ).all()
    assert entries, "private content read by admin power without an audit entry"
