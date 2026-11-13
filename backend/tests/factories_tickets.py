"""Ticket fixtures: `desk` is a team space with one logged-in client per role, plus
helpers to read its statuses and to make tickets through the API.

Clients of `desk`: `manager` (space admin), `moderator`, `editor`, `editor2`,
`viewer`, `outsider` (a member without a role in the space) and `admin` (a system
admin without a membership).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import SpaceRole
from app.core.principal import SystemRole
from app.modules.spaces.models import Space
from app.modules.tickets.models import TicketStatus, WorkItem
from app.modules.users.models import User
from tests.factories import login

ROLES = {
    "manager": SpaceRole.ADMIN,
    "moderator": SpaceRole.MODERATOR,
    "editor": SpaceRole.EDITOR,
    "editor2": SpaceRole.EDITOR,
    "viewer": SpaceRole.VIEWER,
}


@dataclass
class Desk:
    space: Space
    users: dict[str, User] = field(default_factory=dict)
    clients: dict[str, AsyncClient] = field(default_factory=dict)

    @property
    def space_id(self) -> str:
        return str(self.space.id)

    def id_of(self, name: str) -> str:
        return str(self.users[name].id)

    def __getattr__(self, name: str) -> AsyncClient:
        try:
            return self.__dict__["clients"][name]  # type: ignore[no-any-return]
        except KeyError:
            raise AttributeError(name) from None


async def statuses(client: AsyncClient, space_id: object) -> list[dict[str, Any]]:
    r = await client.get(f"/api/spaces/{space_id}/ticket-statuses")
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def status_of(client: AsyncClient, space_id: object, category: str) -> dict[str, Any]:
    """The space's first status of the category."""
    return next(s for s in await statuses(client, space_id) if s["category"] == category)


async def new_ticket(
    client: AsyncClient, space_id: object, title: str = "Ticket", **fields: Any
) -> dict[str, Any]:
    r = await client.post(f"/api/spaces/{space_id}/tickets", json={"title": title, **fields})
    assert r.status_code == 201, r.text
    ticket: dict[str, Any] = r.json()
    return ticket


async def patch(client: AsyncClient, ticket: dict[str, Any], **fields: Any) -> Any:
    """PATCH with the ticket's version; the response."""
    return await client.patch(
        f"/api/tickets/{ticket['number']}", json={"version": ticket["version"], **fields}
    )


@pytest.fixture
async def desk(
    make_user: Callable[..., Awaitable[User]],
    make_space: Callable[..., Awaitable[Space]],
    make_client: Callable[..., Awaitable[AsyncClient]],
) -> Desk:
    users = {name: await make_user(name=f"Desk {name}") for name in ROLES}
    users["outsider"] = await make_user(name="Desk outsider")
    users["admin"] = await make_user(SystemRole.ADMIN, name="Desk admin")
    members = [(users[name], role) for name, role in ROLES.items()]
    space = await make_space("team", "Desk", members=members)
    desk = Desk(space, users)
    for name, user in users.items():
        client = await make_client(csrf=True)
        await login(client, user.email)
        desk.clients[name] = client
    return desk


async def ticket_row(
    session: AsyncSession,
    space: Space,
    reporter: User,
    *,
    status_id: object | None = None,
    number: int | None = None,
    **fields: Any,
) -> WorkItem:
    """A ticket written straight into the table (for tests below the API): the space's
    first `open` status unless `status_id`, the next free number unless `number`."""
    if status_id is None:
        status_id = await session.scalar(
            select(TicketStatus.id)
            .where(TicketStatus.space_id == space.id, TicketStatus.category == "open")
            .order_by(TicketStatus.position)
            .limit(1)
        )
    if number is None:
        taken = await session.scalar(
            select(func.coalesce(func.max(WorkItem.number), 0)).where(
                WorkItem.org_id == space.org_id
            )
        )
        number = int(taken or 0) + 1
    item = WorkItem(
        org_id=space.org_id,
        space_id=space.id,
        number=number,
        kind=fields.pop("kind", "task"),
        title=fields.pop("title", "Row"),
        status_id=status_id,
        priority=fields.pop("priority", "normal"),
        reporter_type="user",
        reporter_id=reporter.id,
        **fields,
    )
    session.add(item)
    await session.flush()
    return item
