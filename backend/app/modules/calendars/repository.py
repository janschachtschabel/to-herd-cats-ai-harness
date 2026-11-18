"""SQL for calendars. Every statement is scoped by the organisation; which spaces a
caller may see comes in as SQL (`core/access.py`), so lists filter in one statement."""

import uuid

from sqlalchemy import Select, and_, exists, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calendars.models import Calendar, CalendarColor
from app.modules.spaces.models import Space, SpaceKind


class CalendarRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def page(
        self, space_ids: Select[uuid.UUID] | list[uuid.UUID], after: uuid.UUID | None, limit: int
    ) -> list[Calendar]:
        """Calendars that are not archived, of the spaces `space_ids`, by id."""
        stmt = (
            select(Calendar)
            .where(
                Calendar.org_id == self.org_id,
                Calendar.archived_at.is_(None),
                Calendar.space_id.in_(space_ids),
            )
            .order_by(Calendar.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(Calendar.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def find(
        self, calendar_id: uuid.UUID, space_ids: Select[uuid.UUID], *, lock: bool = False
    ) -> Calendar | None:
        """The calendar if it is not archived and lies in one of `space_ids`, in one
        statement: one the caller may not see costs what an unknown id costs."""
        stmt = select(Calendar).where(
            Calendar.org_id == self.org_id,
            Calendar.id == calendar_id,
            Calendar.archived_at.is_(None),
            Calendar.space_id.in_(space_ids),
        )
        if lock:
            stmt = stmt.with_for_update(of=Calendar).execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def count_active(self, space_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(
            Calendar.org_id == self.org_id,
            Calendar.space_id == space_id,
            Calendar.archived_at.is_(None),
        )
        return int(await self.session.scalar(stmt) or 0)

    async def add(self, calendar: Calendar) -> Calendar:
        self.session.add(calendar)
        await self.session.flush()
        return calendar

    async def lock_space(self, space_id: uuid.UUID) -> Space | None:
        """The space's row, locked until the transaction ends: calendars of one space
        are made one after the other (the limit, the default)."""
        stmt = (
            select(Space).where(Space.org_id == self.org_id, Space.id == space_id).with_for_update()
        )
        return await self.session.scalar(stmt)

    async def default_of(self, space_id: uuid.UUID) -> Calendar | None:
        """The space's default calendar (never an archived one: a default is kept)."""
        stmt = select(Calendar).where(
            Calendar.org_id == self.org_id,
            Calendar.space_id == space_id,
            Calendar.is_default.is_(True),
            Calendar.archived_at.is_(None),
        )
        return await self.session.scalar(stmt)

    async def insert_default(self, space_id: uuid.UUID, name: str, color: CalendarColor) -> None:
        """The space's default calendar unless it has one (the partial unique index)."""
        await self.session.execute(
            insert(Calendar)
            .values(
                org_id=self.org_id,
                space_id=space_id,
                name=name,
                color=color,
                is_default=True,
                version=1,
            )
            .on_conflict_do_nothing(index_elements=["space_id"], index_where=text("is_default"))
        )

    async def defaults_due(
        self,
        space_ids: Select[uuid.UUID],
        owner_id: uuid.UUID,
        general_name: str,
        *,
        only: uuid.UUID | None = None,
    ) -> list[uuid.UUID]:
        """Of `space_ids` (with `only`: that one space of them): the person's own
        personal space and the general open space, each only while it has no default
        calendar."""
        has_default = exists().where(Calendar.space_id == Space.id, Calendar.is_default.is_(True))
        stmt = select(Space.id).where(
            Space.org_id == self.org_id,
            Space.id.in_(space_ids),
            or_(
                and_(Space.kind == SpaceKind.PERSONAL, Space.owner_user_id == owner_id),
                and_(Space.kind == SpaceKind.OPEN, Space.name == general_name),
            ),
            ~has_default,
        )
        if only is not None:
            stmt = stmt.where(Space.id == only)
        return list((await self.session.scalars(stmt)).all())
