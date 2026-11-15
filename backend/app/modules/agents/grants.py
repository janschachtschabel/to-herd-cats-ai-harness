"""An agent's tool grants as its managers see and set them (plan M6 task 2): every tool
of the catalog with its level and effect, the default the agent's level gives, the
agent's entry and the effective grant (`toolbox/policy.py`). Setting replaces all
entries at once, with the agent's `version` (409 `agent.version_conflict`); a name the
catalog does not list is refused (422 `agent.tool_unknown`). Holders of
`agent.manage` only (404 `agent.not_found` else); every change is audited.
`max_level`: the highest level the caller may give the agent (`may_grant_level`), so
a level they may not give is never offered (a personal agent's and an external
agent's: 2). `via_mcp`: for an external agent, whether a catalog tool can reach its
token over `/mcp` (plan M8 decision 11; `mcp_tools/exposed.py`), so its managers see
which grants count for it.

External tools (plan M8 decision 8, `toolbox/external.py`) follow the catalog: every
usable one of the organisation (approved and unchanged, on an enabled server), and
every other one the agent has an entry for (its `effective` is then `block` and
`usable` false, so the entry is kept but nothing is offered). An external tool is
offered only with an entry (its `default` is `block`); a write tool needs level 4 and
is at most `confirm`. Entries name an external tool by its `ext_…` name; a name that
is no tool of the organisation is refused like an unknown one."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import ValidationFailed
from app.modules.agents.models import EXTERNAL_MAX_LEVEL, MAX_LEVEL, Agent
from app.modules.agents.repository import AgentRepository
from app.modules.agents.service import AgentService
from app.modules.agents.toolbox.base import ToolSpec
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.agents.toolbox.external import every_external
from app.modules.agents.toolbox.policy import (
    FREE_LEVEL,
    Grant,
    default_grant,
    effective,
    may_grant_level,
)
from app.modules.audit.recorder import record
from app.modules.mcp_tools.exposed import reaches_external_agent


@dataclass(frozen=True, slots=True)
class ExternalOf:
    server_id: uuid.UUID
    server_name: str
    tool_id: uuid.UUID
    tool_name: str
    usable: bool


@dataclass(frozen=True, slots=True)
class ToolGrant:
    name: str
    level: int
    effect: str
    default: Grant
    entry: Grant | None
    effective: Grant
    external: ExternalOf | None = None
    via_mcp: bool = False


@dataclass(frozen=True, slots=True)
class AgentTools:
    agent: Agent
    tools: list[ToolGrant]
    max_level: int


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
        externals = {spec.name for spec, _ in await every_external(self.session, actor.org_id)}
        unknown = sorted(set(entries) - set(CATALOG) - externals)
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
        tools = [_grant(agent, spec, stored, None) for spec in CATALOG.values()]
        for spec, usable in await every_external(self.session, actor.org_id):
            if usable or spec.name in stored:
                tools.append(_grant(agent, spec, stored, usable))
        return AgentTools(agent, tools, self.max_level(actor, agent))

    def max_level(self, actor: Actor, agent: Agent) -> int:
        if agent.owner_user_id is not None:  # personal agents stay at 2 (`personal.py`)
            return FREE_LEVEL
        if agent.external:  # it proposes at most (plan M8 decision 11)
            return EXTERNAL_MAX_LEVEL
        return MAX_LEVEL if may_grant_level(actor, MAX_LEVEL) else FREE_LEVEL


def _grant(agent: Agent, spec: ToolSpec, stored: dict[str, str], usable: bool | None) -> ToolGrant:
    """`usable`: None for the catalog's tools; for an external one, whether a run may
    call it now (else it counts as `block`)."""
    entry = Grant(stored[spec.name]) if spec.name in stored else None
    grant = effective(agent.level, spec, entry) if usable is not False else Grant.BLOCK
    remote = spec.remote
    of = None
    if remote is not None:
        of = ExternalOf(
            remote.server_id, remote.server_name, remote.tool_id, remote.tool_name, bool(usable)
        )
    return ToolGrant(
        spec.name,
        spec.level,
        spec.effect.value,
        default_grant(agent.level, spec),
        entry,
        grant,
        of,
        via_mcp=agent.external and remote is None and reaches_external_agent(spec.name),
    )
