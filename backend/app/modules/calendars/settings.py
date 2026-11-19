"""The organisation's calendar switches (plan M10 decision 2), read and set with
`calendar.manage` (admins; everyone else 403), audited when they change: the sync
switch gives `calendar.sync` to every active person but guests. The row's `version`
guards every change (409 `calendar.settings_version_conflict`). Turning a switch tells
every active person (`access.changed`), so their clients reload their rights."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.core.access_events import access_changed
from app.core.errors import Conflict
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.calendars.setting_repository import CalendarSettingRepository
from app.modules.users.repository import UserRepository

FIELDS = ("sync_enabled",)


@dataclass(frozen=True, slots=True)
class CalendarSettings:
    sync_enabled: bool
    version: int


class CalendarSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, actor: Actor) -> CalendarSettings:
        await require(self.session, actor, Action.CALENDAR_MANAGE)
        row = await CalendarSettingRepository(self.session, actor.org_id).get()
        if row is None:
            return CalendarSettings(False, 1)
        return CalendarSettings(row.sync_enabled, row.version)

    async def set(self, actor: Actor, sync_enabled: bool, version: int) -> CalendarSettings:
        await require(self.session, actor, Action.CALENDAR_MANAGE)
        row = await CalendarSettingRepository(self.session, actor.org_id).lock()
        if row.version != version:
            raise Conflict(
                code="calendar.settings_version_conflict",
                details={"current_version": row.version},
            )
        before = snapshot(row, FIELDS)
        row.sync_enabled = sync_enabled
        changed = changes(before, row)
        if changed:
            row.version += 1
            await self.session.flush()
            await record(
                self.session, actor, "calendar.settings_set", "organization", actor.org_id, changed
            )
            everyone = await UserRepository(self.session).active_ids(actor.org_id)
            await access_changed(self.session, actor, everyone, space_id=None)
        return CalendarSettings(row.sync_enabled, row.version)
