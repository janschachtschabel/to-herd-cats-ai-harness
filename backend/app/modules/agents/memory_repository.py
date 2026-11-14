"""The SQL of agent memory (`memory.py`): the row naming an agent's page in a space,
and the memory pages a run may read. Every statement starts from the organisation."""

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.agents.memory_models import AgentMemory
from app.modules.spaces.models import Space
from app.modules.wiki.models import Page


@dataclass(frozen=True, slots=True)
class MemoryPage:
    space_id: uuid.UUID
    space_name: str
    page_id: uuid.UUID
    content_md: str


class MemoryRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def lock(self, agent_id: uuid.UUID, space_id: uuid.UUID) -> None:
        """One writer per agent and space until the transaction ends."""
        await advisory_xact_lock(self.session, f"agent.memory:{agent_id}:{space_id}")

    async def get(self, agent_id: uuid.UUID, space_id: uuid.UUID) -> AgentMemory | None:
        stmt = (
            select(AgentMemory)
            .where(
                AgentMemory.org_id == self.org_id,
                AgentMemory.agent_id == agent_id,
                AgentMemory.space_id == space_id,
            )
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def point(
        self,
        found: AgentMemory | None,
        agent_id: uuid.UUID,
        space_id: uuid.UUID,
        page_id: uuid.UUID,
    ) -> None:
        """The agent's memory in the space is now that page."""
        if found is None:
            found = AgentMemory(
                org_id=self.org_id, agent_id=agent_id, space_id=space_id, page_id=page_id
            )
            self.session.add(found)
        else:
            found.page_id = page_id
        await self.session.flush()

    async def for_run(
        self,
        agent_id: uuid.UUID,
        seen: ColumnElement[bool],
        ai_spaces: Select[uuid.UUID],
        first: uuid.UUID | None,
    ) -> list[MemoryPage]:
        """The agent's memory pages the run may read: pages the actor sees (`seen`:
        its spaces, outside the trash, published or a draft it may see), still in the
        space they are the memory of, not locked for AI, in a space whose policy lets
        the connection receive them (`ai_spaces`). The space `first` first, then by
        space name."""
        stmt = (
            select(Page.space_id, Space.name, Page.id, Page.content_md)
            .join(AgentMemory, AgentMemory.page_id == Page.id)
            .join(Space, Space.id == Page.space_id)
            .where(
                AgentMemory.org_id == self.org_id,
                AgentMemory.agent_id == agent_id,
                Page.space_id == AgentMemory.space_id,
                seen,
                Page.no_ai.is_(False),
                Page.space_id.in_(ai_spaces),
            )
            .order_by(case((Page.space_id == first, 0), else_=1), Space.name, Space.id)
        )
        return [MemoryPage(*row) for row in (await self.session.execute(stmt)).all()]
