"""The spaces an agent is a member of, as its managers see them (plan M6 task 11):
each with the agent's role there, sorted by name, paged by (name, id). Holders of
`agent.manage` only (404 `agent.not_found` else). Open spaces the agent merely reads
are not listed: they are not memberships."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.pagination import Page, PageParams, decode_key_cursor, encode_key_cursor
from app.modules.agents.membership_repository import AgentSpace, AgentSpaceRepository
from app.modules.agents.service import AgentService


class AgentSpaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, actor: Actor, agent_id: uuid.UUID, params: PageParams) -> Page[AgentSpace]:
        agent = await AgentService(self.session).get(actor, agent_id)  # 404 for the rest
        after = decode_key_cursor(params.cursor) if params.cursor else None
        repo = AgentSpaceRepository(self.session, actor.org_id)
        rows = await repo.page(agent.id, after, params.limit + 1)
        more = len(rows) > params.limit
        items = rows[: params.limit]
        last = items[-1] if more and items else None
        cursor = encode_key_cursor(last.name, last.id) if last else None
        return Page[AgentSpace](items=items, next_cursor=cursor)
