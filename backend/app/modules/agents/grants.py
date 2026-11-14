"""An agent's tool grants as its managers see and set them (plan M6 task 2): every tool
of the catalog with its level and effect, the default the agent's level gives, the
agent's entry and the effective grant (`toolbox/policy.py`). Setting replaces all
entries at once, with the agent's `version` (409 `agent.version_conflict`); a name the
catalog does not list is refused (422 `agent.tool_unknown`). Holders of
`agent.manage` only (404 `agent.not_found` else); every change is audited."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import ValidationFailed
from app.modules.agents.models import Agent
from app.modules.agents.repository import AgentRepository
from app.modules.agents.service import AgentService
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.agents.toolbox.policy import Grant, default_grant, effective
from app.modules.audit.recorder import record


@dataclass(frozen=True, slots=True)
class ToolGrant:
    name: str
    level: int
    effect: str
    default: Grant
    entry: Grant | None
    effective: Grant


@dataclass(frozen=True, slots=True)
class AgentTools:
    agent: Agent
    tools: list[ToolGrant]


class GrantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.agents = AgentService(session)

    async def get(self, actor: Actor, agent_id: uuid.UUID) -> AgentTools:
        agent = await self.agents.get(actor, agent_id)
        return await self._shown(actor, agent)

    async def set(
        self, actor: Actor, agent_id: uuid.UUID, entries: dict[str, Grant], version: int
    ) -> AgentTools:
        await self.agents.get(actor, agent_id)  # 404 for those who do not manage agents
        unknown = sorted(set(entries) - set(CATALOG))
        if unknown:
            raise ValidationFailed(code="agent.tool_unknown", details={"tools": unknown})
        agent = await self.agents.current(actor, agent_id, version)
        repo = AgentRepository(self.session, actor.org_id)
        await repo.replace_tool_entries(agent.id, {k: v.value for k, v in entries.items()})
        agent.version += 1
        await self.session.flush()
        details = {"tools": {k: v.value for k, v in sorted(entries.items())}}
        await record(self.session, actor, "agent.tools_changed", "agent", agent.id, details)
        return await self._shown(actor, agent)

    async def _shown(self, actor: Actor, agent: Agent) -> AgentTools:
        stored = await AgentRepository(self.session, actor.org_id).tool_entries(agent.id)
        tools = []
        for spec in CATALOG.values():
            entry = Grant(stored[spec.name]) if spec.name in stored else None
            tools.append(
                ToolGrant(
                    spec.name,
                    spec.level,
                    spec.effect.value,
                    default_grant(agent.level, spec),
                    entry,
                    effective(agent.level, spec, entry),
                )
            )
        return AgentTools(agent, tools)
