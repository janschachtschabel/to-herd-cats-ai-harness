"""Calendars for tests (plan M10): `new_calendar` makes one through the API,
`listed` reads every page of a calendar list, `actor_of` gives a person's actor,
`new_event` makes an event, `window` reads every page of the event window, and the
fixture `private_event` is the one private event every leak test reads (plan M10
review focus 2: each later output path checks it in a `test_private_path_<area>.py`)."""

from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import actor_for
from app.core.actor import Actor
from app.modules.auth.context import AuthContext
from app.modules.spaces.models import Space
from app.modules.users.models import User
from tests.factories import MakeUser, login
from tests.factories_spaces import MakeSpace

# Every word of the private event's content: none may reach anyone but its organiser.
SECRET = "GEHEIM"


async def actor_of(session: AsyncSession, user: User) -> Actor:
    return await actor_for(session, AuthContext(user=user))


async def new_calendar(
    client: AsyncClient, space_id: object, name: str = "Termine", **fields: Any
) -> dict[str, Any]:
    r = await client.post(f"/api/spaces/{space_id}/calendars", json={"name": name, **fields})
    assert r.status_code == 201, r.text
    made: dict[str, Any] = r.json()
    return made


async def listed(client: AsyncClient, url: str = "/api/calendars", limit: int = 100) -> list[Any]:
    """Every item of a calendar list, page by page."""
    items: list[Any] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        r = await client.get(url, params=params)
        assert r.status_code == 200, r.text
        items += r.json()["items"]
        if (cursor := r.json()["next_cursor"]) is None:
            return items


async def new_event(client: AsyncClient, calendar_id: object, **fields: Any) -> dict[str, Any]:
    """An event through the API: one hour on 23 November 2026, 10:00 in Berlin, unless
    `fields` say otherwise."""
    body: dict[str, Any] = {
        "title": "Termin",
        "starts_at": "2026-11-23T10:00:00+01:00",
        "ends_at": "2026-11-23T11:00:00+01:00",
        "time_zone": "Europe/Berlin",
        **fields,
    }
    r = await client.post(f"/api/calendars/{calendar_id}/events", json=body)
    assert r.status_code == 201, r.text
    made: dict[str, Any] = r.json()
    return made


async def window(
    client: AsyncClient, start: str, end: str, limit: int = 100, **params: Any
) -> list[dict[str, Any]]:
    """Every occurrence of the window `[start, end)`, page by page."""
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        query: dict[str, Any] = {"from": start, "to": end, "limit": limit, **params}
        if cursor:
            query["cursor"] = cursor
        r = await client.get("/api/calendar/events", params=query)
        assert r.status_code == 200, r.text
        items += r.json()["items"]
        if (cursor := r.json()["next_cursor"]) is None:
            return items


async def logged_in(make_client: Any, user: User) -> AsyncClient:
    client: AsyncClient = await make_client(csrf=True)
    await login(client, user.email)
    return client


@dataclass
class PrivateEvent:
    """A weekly private event (four Mondays from 23 November 2026, 10:00–11:00 in
    Berlin) in a team calendar: its organiser (an editor) sees everything; a reader of
    the calendar (a viewer) sees only times and "busy"; an outsider sees nothing."""

    space: Space
    calendar: dict[str, Any]
    event: dict[str, Any]
    organiser: User
    reader: User
    outsider: User
    organiser_client: AsyncClient
    reader_client: AsyncClient
    outsider_client: AsyncClient
    # A window holding all four occurrences.
    start: str = "2026-11-16T00:00:00Z"
    end: str = "2026-12-21T00:00:00Z"


@pytest.fixture
async def private_event(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> PrivateEvent:
    organiser, reader, outsider = [await make_user() for _ in range(3)]
    space = await make_space("team", members=[(organiser, "moderator"), (reader, "viewer")])
    organiser_client = await logged_in(make_client, organiser)
    calendar = await new_calendar(organiser_client, space.id, "Team")
    event = await new_event(
        organiser_client,
        calendar["id"],
        title=f"{SECRET}-Titel",
        location=f"{SECRET}-Ort",
        description=f"{SECRET}-Text",
        uid=f"{SECRET}-uid@example.com",
        rrule="FREQ=WEEKLY;COUNT=4",
        visibility="private",
    )
    return PrivateEvent(
        space=space,
        calendar=calendar,
        event=event,
        organiser=organiser,
        reader=reader,
        outsider=outsider,
        organiser_client=organiser_client,
        reader_client=await logged_in(make_client, reader),
        outsider_client=await logged_in(make_client, outsider),
    )
