"""Who holds `mcp.use` (plan M8 decision 5): every active person of the organisation
but guests, while the organisation's switch is on, unless their own AI assignment
expressly keeps them from AI (`no_ai`, spec 7.2): an external client is an AI reading
the organisation's data (plan M8 task 4). It needs no model: a person to whom no
assignment applies holds it. Derived, never stored on the person; the permission
check (`core/access.py`) and the token resolver (`resolve.py`) ask the same rule."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.tokens.repository import McpSettingRepository, McpStanding


def may_use_mcp(standing: McpStanding) -> bool:
    return (
        standing.enabled
        and standing.is_active
        and standing.system_role != SystemRole.GUEST
        and not standing.kept_from_ai
    )


async def holds_mcp_use(session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    found = await McpSettingRepository(session, org_id).standing(user_id)
    return found is not None and may_use_mcp(found)
