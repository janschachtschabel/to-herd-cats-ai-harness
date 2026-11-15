"""The organisation's MCP settings (plan M8 decisions 4 and 5), set with `ai.manage`
(everyone else: 404 `ai.not_found`), audited: the switch that gives `mcp.use` to
every active person but guests, and the data location an MCP client counts as for
the spaces' AI policy (`external` unless the clients run in the house). Both share
the row's `version` (409 `mcp.settings_version_conflict`). Turning the switch tells
every active person (`access.changed`), so their clients reload `mcp.use`."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor
from app.core.access_events import access_changed
from app.core.errors import Conflict
from app.modules.ai.access import require_ai
from app.modules.ai.models import DataLocation
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.tokens.repository import McpSettingRepository
from app.modules.users.repository import UserRepository

FIELDS = ("enabled", "data_location")


@dataclass(frozen=True, slots=True)
class McpSettings:
    enabled: bool
    data_location: DataLocation
    version: int


class McpSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, actor: Actor) -> McpSettings:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        row = await McpSettingRepository(self.session, actor.org_id).get()
        if row is None:
            return McpSettings(False, DataLocation.EXTERNAL, 1)
        return McpSettings(row.enabled, DataLocation(row.data_location), row.version)

    async def set(
        self, actor: Actor, enabled: bool, data_location: DataLocation, version: int
    ) -> McpSettings:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        row = await McpSettingRepository(self.session, actor.org_id).lock()
        if row.version != version:
            raise Conflict(
                code="mcp.settings_version_conflict", details={"current_version": row.version}
            )
        before = snapshot(row, FIELDS)
        row.enabled = enabled
        row.data_location = data_location
        row.version += 1
        await self.session.flush()
        changed = changes(before, row)
        await record(self.session, actor, "mcp.settings_set", "organization", actor.org_id, changed)
        if "enabled" in changed:
            everyone = await UserRepository(self.session).active_ids(actor.org_id)
            await access_changed(self.session, actor, everyone, space_id=None)
        return McpSettings(row.enabled, DataLocation(row.data_location), row.version)
