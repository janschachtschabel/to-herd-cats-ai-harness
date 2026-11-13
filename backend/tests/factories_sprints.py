"""Sprint helpers for the tests (plan M4b task 1): make, start and close sprints through
the API."""

from typing import Any

from httpx import AsyncClient


async def new_sprint(
    client: AsyncClient,
    space_id: object,
    name: str = "Sprint",
    starts_on: str = "2026-11-16",
    ends_on: str = "2026-11-27",
    **fields: Any,
) -> dict[str, Any]:
    r = await client.post(
        f"/api/spaces/{space_id}/sprints",
        json={"name": name, "starts_on": starts_on, "ends_on": ends_on, **fields},
    )
    assert r.status_code == 201, r.text
    sprint: dict[str, Any] = r.json()
    return sprint


async def start(client: AsyncClient, sprint: dict[str, Any]) -> Any:
    """POST start with the sprint's version; the response."""
    return await client.post(
        f"/api/sprints/{sprint['id']}/start", json={"version": sprint["version"]}
    )


async def close(client: AsyncClient, sprint: dict[str, Any], move_open_to: str) -> Any:
    return await client.post(
        f"/api/sprints/{sprint['id']}/close",
        json={"version": sprint["version"], "move_open_to": move_open_to},
    )


async def started(client: AsyncClient, space_id: object, name: str = "Läuft") -> dict[str, Any]:
    """A new sprint, started."""
    r = await start(client, await new_sprint(client, space_id, name))
    assert r.status_code == 200, r.text
    sprint: dict[str, Any] = r.json()
    return sprint


async def sprints(client: AsyncClient, space_id: object, **params: Any) -> list[dict[str, Any]]:
    """Every sprint of the space the client lists, every page."""
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        query = {**params, **({"cursor": cursor} if cursor else {})}
        r = await client.get(f"/api/spaces/{space_id}/sprints", params=query)
        assert r.status_code == 200, r.text
        items += r.json()["items"]
        if (cursor := r.json()["next_cursor"]) is None:
            return items
