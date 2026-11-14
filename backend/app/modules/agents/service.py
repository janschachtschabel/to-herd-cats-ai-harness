"""The organisation's agents (spec 8.1; plan M5 decision 2), managed by holders of
`agent.manage` (everyone else: 404 `agent.not_found`, as for an unknown id).

An agent talks to a chat connection of the organisation, with one of its models; the
connection is locked shared while an agent is written, so it cannot be deleted under
it (the deletion checks agents too, 409 `ai.connection_in_use`). Its responsible
person is an active person, no guest. Limits are capped (25 steps, 10 minutes). An
agent that took part in a conversation or ran is not deleted (409 `agent.in_use`):
it is paused, so its answers stay attributed. Every change is audited (without the
instructions' text, which may be long; their length instead).
"""

import json
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.errors import Conflict, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.core.principal import SystemRole
from app.modules.agents.models import Agent
from app.modules.agents.repository import AgentRepository
from app.modules.agents.schemas import AgentCreate, AgentUpdate
from app.modules.agents.standing import agent_not_found, visible_agent
from app.modules.ai.effective import CHAT_PURPOSES
from app.modules.ai.repository import ConnectionRepository
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.users.repository import UserRepository

_FIELDS = (
    "name",
    "intro",
    "connection_id",
    "model",
    "responsible_user_id",
    "status",
    "max_steps",
    "max_runtime_seconds",
)


async def require_agents(session: AsyncSession, actor: Actor) -> None:
    if not await can(session, actor, Action.AGENT_MANAGE):
        raise agent_not_found()


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def repo(self, actor: Actor) -> AgentRepository:
        return AgentRepository(self.session, actor.org_id)

    async def list(self, actor: Actor, params: PageParams) -> Page[Agent]:
        await require_agents(self.session, actor)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).page(after, params.limit + 1)
        return id_page(rows, params.limit, lambda a: a.id)

    async def get(self, actor: Actor, agent_id: uuid.UUID) -> Agent:
        await require_agents(self.session, actor)
        return _found(await self.repo(actor).get(agent_id))

    async def responsible_names(
        self, actor: Actor, agents: Sequence[Agent]
    ) -> dict[uuid.UUID, str]:
        """For showing agents to someone who may manage them: their responsible
        people's names (the dialog needs no people list for it)."""
        await require_agents(self.session, actor)
        return await self.repo(actor).responsible_names({a.id for a in agents})

    async def profile(self, actor: Actor, agent_id: uuid.UUID) -> Agent:
        """For a person with `ai.use`: an agent that is not a draft."""
        return await visible_agent(self.session, actor, agent_id)

    async def create(self, actor: Actor, data: AgentCreate) -> Agent:
        await require_agents(self.session, actor)
        await self._usable_connection(actor, data.connection_id, data.model)
        await self._responsible(actor, data.responsible_user_id)
        agent = await self.repo(actor).add(
            Agent(
                org_id=actor.org_id,
                name=data.name,
                intro=data.intro,
                instructions=data.instructions,
                connection_id=data.connection_id,
                model=data.model,
                responsible_user_id=data.responsible_user_id,
                status=data.status,
                max_steps=data.max_steps,
                max_runtime_seconds=data.max_runtime_seconds,
            )
        )
        details = {**snapshot(agent, _FIELDS), "instructions_chars": len(agent.instructions)}
        await self._audit(actor, "agent.created", agent, details)
        return agent

    async def update(self, actor: Actor, agent_id: uuid.UUID, data: AgentUpdate) -> Agent:
        await require_agents(self.session, actor)
        agent = await self._current(actor, agent_id, data.version)
        given = data.model_fields_set - {"version"}
        if ("connection_id" in given or "model" in given) and (
            data.connection_id is None or data.model is None
        ):
            raise ValidationFailed(code="agent.connection_and_model")
        if data.connection_id is not None and data.model is not None:
            await self._usable_connection(actor, data.connection_id, data.model)
        if data.responsible_user_id is not None:
            await self._responsible(actor, data.responsible_user_id)
        before = snapshot(agent, _FIELDS)
        for name in given:
            value = getattr(data, name)
            if value is None:
                raise ValidationFailed(f"{name} cannot be null", code="validation_failed")
            setattr(agent, name, value)
        agent.version += 1
        await self.session.flush()
        details: dict[str, Any] = {"changes": changes(before, agent)}
        if "instructions" in given:
            details["instructions_chars"] = len(agent.instructions)
        await self._audit(actor, "agent.updated", agent, details)
        return agent

    async def delete(self, actor: Actor, agent_id: uuid.UUID, version: int) -> None:
        await require_agents(self.session, actor)
        agent = await self._current(actor, agent_id, version)
        repo = self.repo(actor)
        if await repo.in_use(agent.id):
            raise Conflict(code="agent.in_use")
        details = {"name": agent.name}
        await repo.delete(agent)
        await self._audit(actor, "agent.deleted", agent, details)

    async def _current(self, actor: Actor, agent_id: uuid.UUID, version: int) -> Agent:
        agent = _found(await self.repo(actor).get(agent_id, lock=True))
        if agent.version != version:
            raise Conflict(
                code="agent.version_conflict", details={"current_version": agent.version}
            )
        return agent

    async def _usable_connection(self, actor: Actor, connection_id: uuid.UUID, model: str) -> None:
        connection = await ConnectionRepository(self.session, actor.org_id).get_shared(
            connection_id
        )
        if connection is None:
            raise ValidationFailed(code="ai.connection_not_found")
        if connection.purpose not in CHAT_PURPOSES:
            raise ValidationFailed(code="ai.connection_not_chat")
        if model not in connection.models:
            raise ValidationFailed(code="ai.model_unknown")

    async def _responsible(self, actor: Actor, user_id: uuid.UUID) -> None:
        user = await UserRepository(self.session).get(actor.org_id, user_id)
        if user is None or not user.is_active or user.system_role == SystemRole.GUEST:
            raise ValidationFailed(code="agent.responsible_invalid")

    async def _audit(
        self, actor: Actor, action: str, agent: Agent, details: dict[str, Any]
    ) -> None:
        plain = json.loads(json.dumps(details, default=str))  # ids as text
        await record(self.session, actor, action, "agent", agent.id, plain)


def _found(agent: Agent | None) -> Agent:
    if agent is None:
        raise agent_not_found()
    return agent
