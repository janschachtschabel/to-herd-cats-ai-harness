"""Groups for tests: `make_group(name=None, members=())`, `group`, `group_with_member`."""

from collections.abc import Awaitable, Callable, Iterable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.modules.groups.models import Group
from app.modules.groups.repository import GroupRepository
from app.modules.orgs.models import Organization
from app.modules.users.models import User

MakeGroup = Callable[..., Awaitable[Group]]


@pytest.fixture
async def make_group(session: AsyncSession, org: Organization) -> MakeGroup:
    counter = 0
    groups = GroupRepository(session)

    async def _make(name: str | None = None, members: Iterable[User] = ()) -> Group:
        nonlocal counter
        counter += 1
        group = await groups.add(Group(org_id=org.id, name=name or f"Group {counter}"))
        for user in members:
            await groups.add_member(group.id, Principal.user(user.id))
        return group

    return _make


@pytest.fixture
async def group(make_group: MakeGroup) -> Group:
    return await make_group("Redaktion")


@pytest.fixture
async def group_with_member(make_group: MakeGroup, member: User) -> Group:
    return await make_group("Vertrieb", members=[member])
