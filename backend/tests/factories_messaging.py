"""Messaging fixtures: `chat` is a team space with a channel and one logged-in client
per role, plus `post(client, conversation_id, body_md, ...)`.

Clients of `chat`: `viewer`, `viewer2` (both `viewer`), `editor`, `moderator`,
`outsider` (a member without a role in the space) and `admin` (a system admin with
no membership).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.core.permissions import SpaceRole
from app.core.principal import SystemRole
from app.modules.spaces.models import Space
from app.modules.users.models import User
from tests.factories import login

ROLES = ("viewer", "viewer2", "editor", "moderator")


@dataclass
class Chat:
    space: Space
    channel: dict[str, Any]
    users: dict[str, User] = field(default_factory=dict)
    clients: dict[str, AsyncClient] = field(default_factory=dict)

    @property
    def channel_id(self) -> str:
        return str(self.channel["id"])

    @property
    def messages(self) -> str:
        return f"/api/conversations/{self.channel_id}/messages"

    def __getattr__(self, name: str) -> AsyncClient:
        try:
            return self.__dict__["clients"][name]  # type: ignore[no-any-return]
        except KeyError:
            raise AttributeError(name) from None


async def send(
    client: AsyncClient, conversation_id: object, body_md: str, **extra: Any
) -> Response:
    payload = {"body_md": body_md, **{k: str(v) for k, v in extra.items()}}
    return await client.post(f"/api/conversations/{conversation_id}/messages", json=payload)


async def post(
    client: AsyncClient, conversation_id: object, body_md: str, **extra: Any
) -> dict[str, Any]:
    response = await send(client, conversation_id, body_md, **extra)
    assert response.status_code == 201, response.text
    message: dict[str, Any] = response.json()
    return message


@pytest.fixture
async def chat(
    make_user: Callable[..., Awaitable[User]],
    make_space: Callable[..., Awaitable[Space]],
    make_client: Callable[..., Awaitable[AsyncClient]],
) -> Chat:
    users = {role: await make_user(name=f"Chat {role}") for role in ROLES}
    users["outsider"] = await make_user(name="Chat outsider")
    users["admin"] = await make_user(SystemRole.ADMIN, name="Chat admin")
    members = [(users[role], SpaceRole(role.rstrip("2"))) for role in ROLES]
    space = await make_space("team", "Chat", members=members)
    clients = {}
    for name, user in users.items():
        client = await make_client(csrf=True)
        await login(client, user.email)
        clients[name] = client
    response = await clients["moderator"].post(
        f"/api/spaces/{space.id}/channels", json={"name": "plaudern"}
    )
    assert response.status_code == 201, response.text
    return Chat(space, response.json(), users, clients)
