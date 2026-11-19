"""Who holds `calendar.sync` (plan M10 decision 2): every active person of the
organisation but guests, while the organisation's switch is on. Derived, never stored
on the person; the permission check (`core/access.py`) asks this rule."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.calendars.setting_repository import CalendarSettingRepository, SyncStanding


def may_sync(standing: SyncStanding) -> bool:
    return standing.enabled and standing.is_active and standing.system_role != SystemRole.GUEST


async def holds_calendar_sync(session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    found = await CalendarSettingRepository(session, org_id).standing(user_id)
    return found is not None and may_sync(found)
