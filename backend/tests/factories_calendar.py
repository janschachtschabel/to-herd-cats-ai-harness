"""Calendars for tests (plan M10): `new_calendar` makes one through the API,
`listed` reads every page of a calendar list, `actor_of` gives a person's actor."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import actor_for
from app.core.actor import Actor
from app.modules.auth.context import AuthContext
from app.modules.users.models import User


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
