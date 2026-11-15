"""The SQL of `mcp_call` (plan M8 decision 6)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.mcp_tools.models import McpCall


class McpCallRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def add(self, call: McpCall) -> None:
        self.session.add(call)
        await self.session.flush()

    async def page(
        self, token_id: uuid.UUID, before: uuid.UUID | None, limit: int
    ) -> list[McpCall]:
        """The token's calls, newest first."""
        stmt = select(McpCall).where(McpCall.org_id == self.org_id, McpCall.token_id == token_id)
        if before is not None:
            stmt = stmt.where(McpCall.id < before)
        stmt = stmt.order_by(McpCall.id.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())
