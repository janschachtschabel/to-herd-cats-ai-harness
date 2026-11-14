"""Who may talk to an agent, and whether it may run now (plan M5 task 5; spec 5.2,
5.4, 7.2).

A person reaches agents only with `ai.use` (derived; guests never have it): without
it every agent endpoint answers 404 `agent.not_found` and the directory lists none. A
draft agent exists only for those with `agent.manage`.

A message to an agent starts a run only if, at that moment, the person has `ai.use`,
the agent is `active`, its responsible person is active and its connection is enabled,
made for chat and still offers the agent's model. A personal agent (`personal.py`)
answers only its owner, and only while the owner has AI, the organisation allows
personal agents and the agent's connection and model are the owner's. Otherwise the message is kept
without a run and the answer says why, as a code the client words (`Refusal`). The
run checks the same again before every model call (`modules/agents/actor.py`).
"""

import uuid
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.errors import NotFound
from app.modules.agents.models import Agent, AgentStatus
from app.modules.agents.repository import AgentRepository
from app.modules.ai.effective import effective_assignment, personal_agents_allowed


class Refusal(StrEnum):
    AI_UNAVAILABLE = "ai.unavailable"  # the person has no `ai.use`
    AGENT_DRAFT = "agent.draft"
    AGENT_PAUSED = "agent.paused"
    RESPONSIBLE_INACTIVE = "agent.responsible_inactive"
    CONNECTION_UNAVAILABLE = "agent.connection_unavailable"
    THREAD_REPLY = "run.thread_reply"  # replies in a thread do not ask the agent
    RUN_WAITING = "run.waiting"  # the conversation's run waits for a person's answer
    PERSONAL_DISABLED = "agent.personal_disabled"  # the organisation stopped personal agents
    NOT_FOUND = "agent.not_found"  # someone else's personal agent: not there for them


def agent_not_found() -> NotFound:
    return NotFound(code="agent.not_found")


async def visible_agent(session: AsyncSession, actor: Actor, agent_id: uuid.UUID) -> Agent:
    """The agent as someone may address it: with `ai.use`, not a draft, and a personal
    agent only for its owner (admins too: 404 else)."""
    if not await can(session, actor, Action.AI_USE):
        raise agent_not_found()
    agent = await AgentRepository(session, actor.org_id).get(agent_id)
    if agent is None or agent.status == AgentStatus.DRAFT or not owned_by(agent, actor):
        raise agent_not_found()
    return agent


def owned_by(agent: Agent, actor: Actor) -> bool:
    """Whether the actor may talk to the agent as far as ownership goes: anyone to the
    organisation's agents, only its owner to a personal one."""
    return agent.owner_user_id in (None, actor.principal.id)


async def agent_refusal(session: AsyncSession, org_id: uuid.UUID, agent: Agent) -> Refusal | None:
    """Why the agent may not run now (None: it may). A personal agent also needs its
    owner's AI, the organisation's switch, and the owner's connection and model."""
    if agent.owner_user_id is not None:
        why = await _personal_refusal(session, org_id, agent, agent.owner_user_id)
        if why is not None:
            return why
    standing = await AgentRepository(session, org_id).standing(agent)
    if standing.status == AgentStatus.DRAFT:
        return Refusal.AGENT_DRAFT
    if standing.status == AgentStatus.PAUSED:
        return Refusal.AGENT_PAUSED
    if not standing.responsible_active:
        return Refusal.RESPONSIBLE_INACTIVE
    if not (standing.connection_enabled and standing.connection_chat and standing.model_listed):
        return Refusal.CONNECTION_UNAVAILABLE
    return None


async def refusal(session: AsyncSession, actor: Actor, agent: Agent) -> Refusal | None:
    """Why a message of `actor` starts no run of `agent` (None: it does)."""
    if not await can(session, actor, Action.AI_USE):
        return Refusal.AI_UNAVAILABLE
    if not owned_by(agent, actor):
        return Refusal.NOT_FOUND
    return await agent_refusal(session, actor.org_id, agent)


async def _personal_refusal(
    session: AsyncSession, org_id: uuid.UUID, agent: Agent, owner: uuid.UUID
) -> Refusal | None:
    target = await effective_assignment(session, org_id, owner)
    if target is None:
        return Refusal.AI_UNAVAILABLE
    if not await personal_agents_allowed(session, org_id):
        return Refusal.PERSONAL_DISABLED
    if (target.connection_id, target.model) != (agent.connection_id, agent.model):
        return Refusal.CONNECTION_UNAVAILABLE
    return None
