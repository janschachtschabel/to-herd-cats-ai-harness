"""Default calendars (plan M10 decision 2, review of task 1): a default is kept (never
archived), counts within the limit of 20, and is stored without a name until someone
renames it (the interface names it in the reader's language)."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from tests.factories import MakeUser, login
from tests.factories_calendar import listed, new_calendar
from tests.factories_spaces import MakeSpace


async def _client(make_client: Any, user: User) -> AsyncClient:
    client: AsyncClient = await make_client(csrf=True)
    await login(client, user.email)
    return client


async def test_a_default_calendar_cannot_be_archived(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """R1-I1: archiving „Mein Kalender“ or the general space's calendar answers 409
    `calendar.default_kept`; the calendar stays, at its version."""
    person = await make_user()
    await make_space("open", "Allgemein", members=[(person, "moderator")])
    client = await _client(make_client, person)
    defaults = await listed(client)
    assert len(defaults) == 2 and all(c["is_default"] for c in defaults)
    for calendar in defaults:
        url = f"/api/calendars/{calendar['id']}"
        r = await client.delete(url, params={"version": calendar["version"]})
        assert (r.status_code, r.json()["error"]["code"]) == (409, "calendar.default_kept")
    assert await listed(client) == defaults
    team = await make_space("team", members=[(person, "moderator")])
    other = await new_calendar(client, team.id)
    r = await client.delete(f"/api/calendars/{other['id']}", params={"version": 1})
    assert r.status_code == 204  # other calendars are archived as before
