"""Who holds `mcp.use` (plan M8 decision 5): every active person of the organisation
but guests, while the organisation's switch is on. Derived, never stored on the
person; the permission check (`core/access.py`) and the token resolver
(`resolve.py`) ask the same rule."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.tokens.repository import McpSettingRepository


def may_use_mcp(is_active: bool, system_role: SystemRole, enabled: bool) -> bool:
    return enabled and is_active and system_role != SystemRole.GUEST


async def holds_mcp_use(session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    found = await McpSettingRepository(session, org_id).standing(user_id)
    return found is not None and may_use_mcp(*found)
