"""Spaces for tests: `make_space(kind, name=None, members=())`, `team_space`,
`open_space`, and `personal_space_of(session, user)`.

`make_user` (tests/factories.py) gives every person a personal space, as
`UserService.create` does.
"""

from collections.abc import Awaitable, Callable, Iterable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.groups.models import Group
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository
from app.modules.users.models import User

MakeSpace = Callable[..., Awaitable[Space]]
Holder = User | Group


def principal_of(holder: Holder) -> Principal:
    return Principal.user(holder.id) if isinstance(holder, User) else Principal.group(holder.id)


async def personal_space_of(session: AsyncSession, user: User) -> Space:
    space = await SpaceRepository(session).get_personal(user.org_id, user.id)
    assert space is not None
    return space


@pytest.fixture
async def make_space(session: AsyncSession, org: Organization) -> MakeSpace:
    counter = 0
    spaces = SpaceRepository(session)

    async def _make(
        kind: SpaceKind | str = SpaceKind.TEAM,
        name: str | None = None,
        members: Iterable[tuple[Holder, SpaceRole | str]] = (),
    ) -> Space:
        nonlocal counter
        counter += 1
        space = await spaces.add(
            Space(
                org_id=org.id,
                kind=SpaceKind(kind),
                name=name or f"Space {counter}",
            )
        )
        for holder, role in members:
            await spaces.set_member(space.id, principal_of(holder), SpaceRole(role))
        return space

    return _make


@pytest.fixture
async def team_space(make_space: MakeSpace) -> Space:
    return await make_space(SpaceKind.TEAM, "Projekt Apfel")


@pytest.fixture
async def open_space(make_space: MakeSpace) -> Space:
    return await make_space(SpaceKind.OPEN, "Handbuch")
