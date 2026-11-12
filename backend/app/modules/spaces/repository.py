import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, delete, exists, false, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.core.repository import BaseRepository, advisory_xact_lock
from app.modules.spaces.models import Space, SpaceMember


def held_by(principals: Sequence[Principal]) -> ColumnElement[bool]:
    """Membership rows of any of `principals` (none: matches nothing)."""
    return or_(
        false(),
        *[
            (SpaceMember.member_type == p.type) & (SpaceMember.member_id == p.id)
            for p in principals
        ],
    )


class SpaceRepository(BaseRepository[Space]):
    model = Space

    async def lock_slugs(self, org_id: uuid.UUID) -> None:
        """Serialise slug allocation in an organisation (find a free one, then insert)."""
        await advisory_xact_lock(self.session, f"spaces:{org_id}")

    async def slug_taken(self, org_id: uuid.UUID, slug: str) -> bool:
        stmt = select(exists().where(Space.org_id == org_id, Space.slug == slug))
        return bool(await self.session.scalar(stmt))

    async def get_for_update(self, org_id: uuid.UUID, space_id: uuid.UUID) -> Space | None:
        """The row as committed now, locked until the transaction ends."""
        stmt = (
            select(Space)
            .where(Space.org_id == org_id, Space.id == space_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def get_personal(self, org_id: uuid.UUID, user_id: uuid.UUID) -> Space | None:
        stmt = select(Space).where(Space.org_id == org_id, Space.owner_user_id == user_id)
        return await self.session.scalar(stmt)

    async def page_among(
        self, ids: Select[uuid.UUID], after: uuid.UUID | None, limit: int
    ) -> list[Space]:
        stmt = select(Space).where(Space.id.in_(ids)).order_by(Space.id).limit(limit)
        if after is not None:
            stmt = stmt.where(Space.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def member_page(
        self, space_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[SpaceMember]:
        stmt = (
            select(SpaceMember)
            .where(SpaceMember.space_id == space_id)
            .order_by(SpaceMember.member_id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(SpaceMember.member_id > after)
        return list((await self.session.scalars(stmt)).all())

    async def set_member(
        self, space_id: uuid.UUID, principal: Principal, role: SpaceRole
    ) -> SpaceMember:
        """Add or change a membership; safe under concurrent requests."""
        stmt = (
            insert(SpaceMember)
            .values(
                space_id=space_id, member_type=principal.type, member_id=principal.id, role=role
            )
            .on_conflict_do_update(
                index_elements=["space_id", "member_type", "member_id"], set_={"role": role}
            )
            .returning(SpaceMember)
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).one()

    async def remove_member(self, space_id: uuid.UUID, principal: Principal) -> bool:
        stmt = (
            delete(SpaceMember)
            .where(SpaceMember.space_id == space_id, held_by([principal]))
            .returning(SpaceMember.member_id)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def delete_memberships_of(self, principal: Principal) -> None:
        await self.session.execute(delete(SpaceMember).where(held_by([principal])))
