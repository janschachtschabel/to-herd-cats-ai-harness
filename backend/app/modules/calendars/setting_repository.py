"""SQL for the organisation's calendar switches (`calendar_setting`, one row per
organisation, missing means off)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import false, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.calendars.models import CalendarSetting
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class SyncStanding:
    """What decides a person's `calendar.sync` (`standing.may_sync`)."""

    is_active: bool
    system_role: SystemRole
    enabled: bool


class CalendarSettingRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def get(self) -> CalendarSetting | None:
        stmt = select(CalendarSetting).where(CalendarSetting.org_id == self.org_id)
        return await self.session.scalar(stmt)

    async def standing(self, user_id: uuid.UUID) -> SyncStanding | None:
        """The person's activity and role and the switch, in one statement (None: no
        such person here)."""
        stmt = (
            select(
                User.is_active,
                User.system_role,
                func.coalesce(CalendarSetting.sync_enabled, false()),
            )
            .outerjoin(CalendarSetting, CalendarSetting.org_id == User.org_id)
            .where(User.org_id == self.org_id, User.id == user_id)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return SyncStanding(bool(row[0]), SystemRole(row[1]), bool(row[2]))

    async def lock(self) -> CalendarSetting:
        """The row, created at version 1 if missing, locked until the transaction ends."""
        await self.session.execute(
            insert(CalendarSetting)
            .values(org_id=self.org_id, version=1)
            .on_conflict_do_nothing(index_elements=["org_id"])
        )
        stmt = (
            select(CalendarSetting)
            .where(CalendarSetting.org_id == self.org_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).one()
