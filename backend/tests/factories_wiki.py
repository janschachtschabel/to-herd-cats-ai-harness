"""Wiki fixtures: `wiki` is a team space with one logged-in client per role, plus
`new_page(client, space_id, title, ...)` and `publish(client, page)`.

Clients of `wiki`: `editor`, `editor2` (both `editor`), `viewer`, `moderator`,
`outsider` (a member without a role in the space) and `admin` (a system admin with
no membership).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.permissions import SpaceRole
from app.core.principal import SystemRole
from app.modules.spaces.models import Space
from app.modules.users.models import User
from tests.factories import login

ROLES = ("editor", "editor2", "viewer", "moderator")


@dataclass
class Wiki:
    space: Space
    users: dict[str, User] = field(default_factory=dict)
    clients: dict[str, AsyncClient] = field(default_factory=dict)

    @property
    def space_id(self) -> str:
        return str(self.space.id)

    def __getattr__(self, name: str) -> AsyncClient:
        try:
            return self.__dict__["clients"][name]  # type: ignore[no-any-return]
        except KeyError:
            raise AttributeError(name) from None


async def new_page(
    client: AsyncClient,
    space_id: object,
    title: str,
    *,
    parent_id: object | None = None,
    content_md: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": title, "content_md": content_md}
    if parent_id is not None:
        body["parent_id"] = str(parent_id)
    r = await client.post(f"/api/spaces/{space_id}/pages", json=body)
    assert r.status_code == 201, r.text
    page: dict[str, Any] = r.json()
    return page


async def publish(client: AsyncClient, page: dict[str, Any]) -> dict[str, Any]:
    r = await client.post(f"/api/pages/{page['id']}/publish", json={"version": page["version"]})
    assert r.status_code == 200, r.text
    published: dict[str, Any] = r.json()
    return published


@pytest.fixture
async def wiki(
    make_user: Callable[..., Awaitable[User]],
    make_space: Callable[..., Awaitable[Space]],
    make_client: Callable[..., Awaitable[AsyncClient]],
) -> Wiki:
    users = {role: await make_user(name=f"Wiki {role}") for role in ROLES}
    users["outsider"] = await make_user(name="Wiki outsider")
    users["admin"] = await make_user(SystemRole.ADMIN, name="Wiki admin")
    members = [(users[role], SpaceRole(role.rstrip("2"))) for role in ROLES]
    space = await make_space("team", "Wiki", members=members)
    wiki = Wiki(space, users)
    for name, user in users.items():
        client = await make_client(csrf=True)
        await login(client, user.email)
        wiki.clients[name] = client
    return wiki
