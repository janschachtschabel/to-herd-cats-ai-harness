"""A group deleted while someone adds it to a space leaves no membership behind (R14).

Two real transactions: the deletion holds its locks, uncommitted, while the addition
runs. The addition must wait for it and then find the group gone."""

import asyncio

import pytest
from sqlalchemy import func, select

from app.core.actor import Actor
from app.core.errors import NotFound
from app.core.permissions import SpaceRole
from app.core.principal import Principal, PrincipalType, SystemRole
from app.modules.groups.models import Group
from app.modules.groups.service import GroupService
from app.modules.spaces.models import Space, SpaceKind, SpaceMember
from app.modules.spaces.service import SpaceService
from app.modules.users.models import User
from tests.real_db import RealDb


async def test_adding_a_group_that_is_being_deleted_leaves_nothing(real_db: RealDb) -> None:
    factory = real_db.database.session_factory
    async with factory() as s:
        owner = (await s.scalars(select(User).where(User.email == real_db.owner_email))).one()
        group = Group(org_id=real_db.org_id, name="Weg")
        space = Space(org_id=real_db.org_id, kind=SpaceKind.TEAM, name="Ziel")
        s.add_all([group, space])
        await s.flush()
        s.add(
            SpaceMember(
                space_id=space.id,
                member_type=PrincipalType.USER,
                member_id=owner.id,
                role=SpaceRole.ADMIN,
            )
        )
        await s.commit()
    actor = Actor(real_db.org_id, Principal.user(owner.id), SystemRole.OWNER, frozenset())

    async with factory() as deleting, factory() as adding:
        await GroupService(deleting).delete(actor, group.id)  # locks held, not committed

        async def add() -> None:
            await SpaceService(adding).set_member(
                actor, space.id, PrincipalType.GROUP, group.id, SpaceRole.EDITOR
            )
            await adding.commit()

        task = asyncio.create_task(add())
        await asyncio.sleep(0.3)
        waited = not task.done()
        await deleting.commit()
        with pytest.raises(NotFound):
            await task
        assert waited

    async with factory() as s:
        orphans = (
            select(func.count())
            .select_from(SpaceMember)
            .where(
                SpaceMember.member_type == PrincipalType.GROUP, SpaceMember.member_id == group.id
            )
        )
        assert await s.scalar(orphans) == 0
