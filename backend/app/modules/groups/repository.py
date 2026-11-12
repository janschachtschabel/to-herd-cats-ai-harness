import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.core.principal import Principal
from app.core.repository import BaseRepository, advisory_xact_lock
from app.modules.groups.models import Group, GroupMember


class GroupRepository(BaseRepository[Group]):
    model = Group

    async def lock_writes(self, org_id: uuid.UUID) -> None:
        """Serialise changes to an organisation's groups (name check, version check)."""
        await advisory_xact_lock(self.session, f"groups:{org_id}")

    async def get_current(self, org_id: uuid.UUID, group_id: uuid.UUID) -> Group | None:
        """The row as committed now, even if this session loaded it earlier."""
        stmt = (
            select(Group)
            .where(Group.org_id == org_id, Group.id == group_id)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def get_by_name(self, org_id: uuid.UUID, name: str) -> Group | None:
        return await self.session.scalar(
            select(Group).where(Group.org_id == org_id, Group.name == name)
        )

    async def page(self, org_id: uuid.UUID, after: uuid.UUID | None, limit: int) -> list[Group]:
        stmt = select(Group).where(Group.org_id == org_id).order_by(Group.id).limit(limit)
        if after is not None:
            stmt = stmt.where(Group.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def member_page(
        self, group_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[GroupMember]:
        stmt = (
            select(GroupMember)
            .where(GroupMember.group_id == group_id)
            .order_by(GroupMember.member_id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(GroupMember.member_id > after)
        return list((await self.session.scalars(stmt)).all())

    async def add_member(self, group_id: uuid.UUID, principal: Principal) -> bool:
        """Idempotent, also under concurrent requests; True if the member is new."""
        stmt = (
            insert(GroupMember)
            .values(group_id=group_id, member_type=principal.type, member_id=principal.id)
            .on_conflict_do_nothing()
            .returning(GroupMember.member_id)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def remove_member(self, group_id: uuid.UUID, principal: Principal) -> bool:
        stmt = (
            delete(GroupMember)
            .where(
                GroupMember.group_id == group_id,
                GroupMember.member_type == principal.type,
                GroupMember.member_id == principal.id,
            )
            .returning(GroupMember.member_id)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def group_ids_for(self, principal: Principal) -> frozenset[uuid.UUID]:
        stmt = select(GroupMember.group_id).where(
            GroupMember.member_type == principal.type, GroupMember.member_id == principal.id
        )
        return frozenset((await self.session.scalars(stmt)).all())
