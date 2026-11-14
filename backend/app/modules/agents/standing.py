"""Who may talk to an agent, and whether it may run now (plan M5 task 5; spec 5.2,
5.4, 7.2).

A person reaches agents only with `ai.use` (derived; guests never have it): without
it every agent endpoint answers 404 `agent.not_found` and the directory lists none. A
draft agent exists only for those with `agent.manage`.

A message to an agent starts a run only if, at that moment, the person has `ai.use`,
the agent is `active`, its responsible person is active and its connection is enabled,
made for chat and still offers the agent's model. Otherwise the message is kept
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


class Refusal(StrEnum):
    AI_UNAVAILABLE = "ai.unavailable"  # the person has no `ai.use`
    AGENT_DRAFT = "agent.draft"
    AGENT_PAUSED = "agent.paused"
    RESPONSIBLE_INACTIVE = "agent.responsible_inactive"
    CONNECTION_UNAVAILABLE = "agent.connection_unavailable"
    THREAD_REPLY = "run.thread_reply"  # replies in a thread do not ask the agent


def agent_not_found() -> NotFound:
    return NotFound(code="agent.not_found")


async def visible_agent(session: AsyncSession, actor: Actor, agent_id: uuid.UUID) -> Agent:
    """The agent as someone may address it: with `ai.use`, not a draft (404 else)."""
    if not await can(session, actor, Action.AI_USE):
        raise agent_not_found()
    agent = await AgentRepository(session, actor.org_id).get(agent_id)
    if agent is None or agent.status == AgentStatus.DRAFT:
        raise agent_not_found()
    return agent


async def agent_refusal(session: AsyncSession, org_id: uuid.UUID, agent: Agent) -> Refusal | None:
    """Why the agent may not run now (None: it may)."""
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
    return await agent_refusal(session, actor.org_id, agent)
