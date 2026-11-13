"""Direct-message fixtures: `people` are logged-in clients of one organisation, plus
`open_dm(client, *users)` and `dm_of(client, *users)`.

People: `alice`, `bob`, `carol` (members), `gast` (a guest) and `admin` (a system
admin who takes part in no conversation).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.core.principal import SystemRole
from app.modules.users.models import User
from tests.factories import login

DMS = "/api/dms"


@dataclass
class People:
    users: dict[str, User] = field(default_factory=dict)
    clients: dict[str, AsyncClient] = field(default_factory=dict)

    def id(self, name: str) -> str:
        return str(self.users[name].id)

    def __getattr__(self, name: str) -> AsyncClient:
        try:
            return self.__dict__["clients"][name]  # type: ignore[no-any-return]
        except KeyError:
            raise AttributeError(name) from None


async def open_dm(client: AsyncClient, *user_ids: object) -> Response:
    return await client.post(DMS, json={"user_ids": [str(u) for u in user_ids]})


async def dm_of(client: AsyncClient, *user_ids: object) -> dict[str, Any]:
    """The conversation of the caller with `user_ids` (opened if new)."""
    response = await open_dm(client, *user_ids)
    assert response.status_code in (200, 201), response.text
    conversation: dict[str, Any] = response.json()
    return conversation


@pytest.fixture
async def people(
    make_user: Callable[..., Awaitable[User]],
    make_client: Callable[..., Awaitable[AsyncClient]],
) -> People:
    roles = {
        "alice": SystemRole.MEMBER,
        "bob": SystemRole.MEMBER,
        "carol": SystemRole.MEMBER,
        "gast": SystemRole.GUEST,
        "admin": SystemRole.ADMIN,
    }
    result = People()
    for name, role in roles.items():
        user = await make_user(role, name=name.title())
        client = await make_client(csrf=True)
        await login(client, user.email)
        result.users[name], result.clients[name] = user, client
    return result
