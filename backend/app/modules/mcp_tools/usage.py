"""A token's usage (plan M8 decision 6): its tool calls through `/mcp`, newest first,
for its person (with `mcp.use`, otherwise 404 `token.not_found` as for someone else's
token) and for the AI administration (`ai.manage`, otherwise 404 `ai.not_found`).
Metadata only: tool, outcome, duration and time."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.mcp_tools.models import McpCall
from app.modules.mcp_tools.repository import McpCallRepository
from app.modules.tokens.service import TokenService


class McpUsageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def mine(self, actor: Actor, token_id: uuid.UUID, params: PageParams) -> Page[McpCall]:
        token = await TokenService(self.session).own(actor, token_id)
        return await self._page(actor, token.id, params)

    async def any(self, actor: Actor, token_id: uuid.UUID, params: PageParams) -> Page[McpCall]:
        token = await TokenService(self.session).any_of_org(actor, token_id)
        return await self._page(actor, token.id, params)

    async def _page(self, actor: Actor, token_id: uuid.UUID, params: PageParams) -> Page[McpCall]:
        before = decode_id_cursor(params.cursor) if params.cursor else None
        repo = McpCallRepository(self.session, actor.org_id)
        rows = await repo.page(token_id, before, params.limit + 1)
        return id_page(rows, params.limit, lambda call: call.id)
