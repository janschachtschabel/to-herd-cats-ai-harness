"""Agents (spec 8.1; plan M5 decision 2): the organisation's, managed by holders of
`agent.manage`, and personal ones, managed by their owners too (`personal.py`);
everyone else gets 404 `agent.not_found`, as for an unknown id.

An agent talks to a chat connection of the organisation, with one of its models; the
connection is locked shared while an agent is written, so it cannot be deleted under
it (the deletion checks agents too, 409 `ai.connection_in_use`). Its responsible
person is an active person, no guest. Limits are capped (25 steps, 10 minutes). Its
level (1 to 4, default 2) above 2 only from an admin or someone who manages every
space of the agent (403 `agent.level_denied`, `toolbox/policy.py`). An
agent that took part in a conversation or ran is not deleted (409 `agent.in_use`):
it is paused, so its answers stay attributed. Every change is audited (without the
instructions' text, which may be long; their length instead).

An external agent (plan M8 decision 11, `kind = external`) is made only with
`agent.manage`: no connection or model, never personal, level at most 2 (422
`agent.external_invalid`, also for such a change later); its kind never changes.
"""

import json
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.errors import Conflict, Forbidden, ValidationFailed
from app.core.models_base import utcnow
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.core.principal import SystemRole
from app.modules.agents.models import EXTERNAL_MAX_LEVEL, Agent, AgentKind
from app.modules.agents.personal import (
    check_given,
    join_home,
    may_manage,
    note_admin_access,
    owners_target,
    require_personal_right,
    within_limit,
)
from app.modules.agents.repository import AgentRepository
from app.modules.agents.schemas import AgentCreate, AgentUpdate
from app.modules.agents.standing import agent_not_found, visible_agent
from app.modules.agents.toolbox.policy import may_grant_level
from app.modules.ai.effective import CHAT_PURPOSES
from app.modules.ai.repository import ConnectionRepository
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.tokens.repository import TokenRepository
from app.modules.users.repository import UserRepository

_FIELDS = (
    "name",
    "kind",
    "owner_user_id",
    "intro",
    "connection_id",
    "model",
    "responsible_user_id",
    "status",
    "max_steps",
    "max_runtime_seconds",
    "level",
)


def external_invalid() -> ValidationFailed:
    return ValidationFailed(
        "An external agent has no connection or model, is nobody's own and has level 2 at most",
        code="agent.external_invalid",
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
        """Every agent for `agent.manage`; one's own personal agents with `ai.use`."""
        after = decode_id_cursor(params.cursor) if params.cursor else None
        if await can(self.session, actor, Action.AGENT_MANAGE):
            owner = None
        elif await can(self.session, actor, Action.AI_USE):
            owner = actor.principal.id
        else:
            raise agent_not_found()
        rows = await self.repo(actor).page(after, params.limit + 1, owner=owner)
        page = id_page(rows, params.limit, lambda a: a.id)
        await note_admin_access(self.session, actor, page.items)
        return page

    async def get(self, actor: Actor, agent_id: uuid.UUID) -> Agent:
        agent = await self._managed(actor, await self.repo(actor).get(agent_id))
        await note_admin_access(self.session, actor, [agent])
        return agent

    async def responsible_names(
        self, actor: Actor, agents: Sequence[Agent]
    ) -> dict[uuid.UUID, str]:
        """For showing agents to someone who may manage them (the caller found them
        through this service): their responsible people's names."""
        return await self.repo(actor).responsible_names({a.id for a in agents})

    async def profile(self, actor: Actor, agent_id: uuid.UUID) -> Agent:
        """For a person with `ai.use`: an agent that is not a draft."""
        return await visible_agent(self.session, actor, agent_id)

    async def create(self, actor: Actor, data: AgentCreate) -> Agent:
        if data.kind == AgentKind.EXTERNAL:
            return await self._create_external(actor, data)
        owner = actor.principal.id if data.personal else None
        if owner is not None:
            await require_personal_right(self.session, actor)
            target = await owners_target(self.session, actor.org_id, owner)
            if target is None:  # `agent.create_personal` holds `ai.use`
                raise agent_not_found()
            check_given(
                target,
                owner,
                connection_id=data.connection_id,
                model=data.model,
                responsible_user_id=data.responsible_user_id,
                level=data.level,
            )
            connection_id, model, responsible = target.connection_id, target.model, owner
        else:
            await require_agents(self.session, actor)
            if data.connection_id is None or data.model is None:
                raise ValidationFailed(code="agent.connection_and_model")
            if data.responsible_user_id is None:
                raise ValidationFailed(code="agent.responsible_invalid")
            connection_id, model = data.connection_id, data.model
            responsible = data.responsible_user_id
            self._level(actor, data.level)
        await self._usable_connection(actor, connection_id, model)
        await self._responsible(actor, responsible)
        if owner is not None:
            await within_limit(self.session, actor.org_id, owner)
        agent = await self.repo(actor).add(
            Agent(
                org_id=actor.org_id,
                name=data.name,
                intro=data.intro,
                instructions=data.instructions,
                connection_id=connection_id,
                model=model,
                responsible_user_id=responsible,
                owner_user_id=owner,
                status=data.status,
                max_steps=data.max_steps,
                max_runtime_seconds=data.max_runtime_seconds,
                level=data.level,
            )
        )
        if owner is not None:
            await join_home(self.session, agent)
        details = {**snapshot(agent, _FIELDS), "instructions_chars": len(agent.instructions)}
        await self._audit(actor, "agent.created", agent, details)
        return agent

    async def _create_external(self, actor: Actor, data: AgentCreate) -> Agent:
        """An external agent (plan M8 decision 11): `agent.manage`, no connection or
        model, not personal, level at most 2, a responsible person."""
        await require_agents(self.session, actor)
        if data.personal or data.connection_id is not None or data.model is not None:
            raise external_invalid()
        if data.level > EXTERNAL_MAX_LEVEL:
            raise external_invalid()
        if data.responsible_user_id is None:
            raise ValidationFailed(code="agent.responsible_invalid")
        await self._responsible(actor, data.responsible_user_id)
        agent = await self.repo(actor).add(
            Agent(
                org_id=actor.org_id,
                kind=AgentKind.EXTERNAL,
                name=data.name,
                intro=data.intro,
                instructions=data.instructions,
                responsible_user_id=data.responsible_user_id,
                status=data.status,
                max_steps=data.max_steps,
                max_runtime_seconds=data.max_runtime_seconds,
                level=data.level,
            )
        )
        details = {**snapshot(agent, _FIELDS), "instructions_chars": len(agent.instructions)}
        await self._audit(actor, "agent.created", agent, details)
        return agent

    async def update(self, actor: Actor, agent_id: uuid.UUID, data: AgentUpdate) -> Agent:
        agent = await self._current(actor, agent_id, data.version)
        given = data.model_fields_set - {"version"}
        if agent.external and (
            {"connection_id", "model"} & given
            or (data.level is not None and data.level > EXTERNAL_MAX_LEVEL)
        ):
            raise external_invalid()
        if ("connection_id" in given or "model" in given) and (
            data.connection_id is None or data.model is None
        ):
            raise ValidationFailed(code="agent.connection_and_model")
        target = None
        if agent.owner_user_id is not None:
            target = await owners_target(self.session, actor.org_id, agent.owner_user_id)
            check_given(
                target,
                agent.owner_user_id,
                connection_id=data.connection_id,
                model=data.model,
                responsible_user_id=data.responsible_user_id,
                level=data.level,
            )
            if target is not None:
                await self._usable_connection(actor, target.connection_id, target.model)
        elif data.connection_id is not None and data.model is not None:
            await self._usable_connection(actor, data.connection_id, data.model)
        if data.responsible_user_id is not None:
            await self._responsible(actor, data.responsible_user_id)
        if data.level is not None and data.level > agent.level:
            self._level(actor, data.level)
        before = snapshot(agent, _FIELDS)
        for name in given:
            value = getattr(data, name)
            if value is None:
                raise ValidationFailed(f"{name} cannot be null", code="validation_failed")
            setattr(agent, name, value)
        if target is not None:  # a personal agent follows its owner's model
            agent.connection_id, agent.model = target.connection_id, target.model
        agent.version += 1
        await self.session.flush()
        details: dict[str, Any] = {"changes": changes(before, agent)}
        if "instructions" in given:
            details["instructions_chars"] = len(agent.instructions)
        if agent.external and "responsible_user_id" in details["changes"]:
            # its tokens were the former person's: never valid again (review M8 1, F9)
            tokens = TokenRepository(self.session)
            details["tokens_revoked"] = await tokens.revoke_of_agent(
                actor.org_id, agent.id, utcnow()
            )
        await self._audit(actor, "agent.updated", agent, details)
        return agent

    async def delete(self, actor: Actor, agent_id: uuid.UUID, version: int) -> None:
        agent = await self._current(actor, agent_id, version)
        repo = self.repo(actor)
        if await repo.in_use(agent.id):
            raise Conflict(code="agent.in_use")
        details = {"name": agent.name}
        await repo.delete(agent)
        await self._audit(actor, "agent.deleted", agent, details)

    async def current(self, actor: Actor, agent_id: uuid.UUID, version: int) -> Agent:
        """The agent locked, at `version` (409 `agent.version_conflict` else)."""
        return await self._current(actor, agent_id, version)

    async def _current(self, actor: Actor, agent_id: uuid.UUID, version: int) -> Agent:
        agent = await self._managed(actor, await self.repo(actor).get(agent_id, lock=True))
        if agent.version != version:
            raise Conflict(
                code="agent.version_conflict", details={"current_version": agent.version}
            )
        return agent

    async def _managed(self, actor: Actor, agent: Agent | None) -> Agent:
        if agent is None or not await may_manage(self.session, actor, agent):
            raise agent_not_found()
        return agent

    def _level(self, actor: Actor, level: int) -> None:
        if not may_grant_level(actor, level):
            raise Forbidden(code="agent.level_denied")

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
