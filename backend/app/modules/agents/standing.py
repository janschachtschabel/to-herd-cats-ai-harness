"""Who may talk to an agent, and whether it may run now (plan M5 task 5; spec 5.2,
5.4, 7.2).

A person reaches agents only with `ai.use` (derived; guests never have it): without
it every agent endpoint answers 404 `agent.not_found` and the directory lists none. A
draft agent exists only for those with `agent.manage`.

A message to an agent starts a run only if, at that moment, the person has `ai.use`,
the agent is `active`, its responsible person is active and its connection is enabled,
made for chat and still offers the agent's model. A personal agent (`personal.py`)
answers only its owner, and only while the owner has AI and the organisation allows
personal agents; it runs on the owner's connection and model as they are when the
run starts (`run_target`), so an admin's change of the owner's assignment applies
from the next run without saving the agent (review M6 finding 13). Otherwise the
message is kept
without a run and the answer says why, as a code the client words (`Refusal`). The
run checks the same again before every model call (`modules/agents/actor.py`).
"""

import uuid
from dataclasses import dataclass
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
    RUN_WAITING = "run.waiting"  # the place has a run that answers first (one at a time)
    PERSONAL_DISABLED = "agent.personal_disabled"  # the organisation stopped personal agents
    NOT_FOUND = "agent.not_found"  # someone else's personal agent: not there for them
    HANDOVER_LIMIT = "run.handover_limit"  # a run at the chain's end hands over no more


@dataclass(frozen=True, slots=True)
class Target:
    connection_id: uuid.UUID
    model: str


async def run_target(session: AsyncSession, org_id: uuid.UUID, agent: Agent) -> Target | None:
    """The connection and model a run of the agent uses now: an organisation agent's
    own; a personal agent's owner's effective assignment (None: the owner has no AI)."""
    if agent.owner_user_id is None:
        return Target(agent.connection_id, agent.model)
    found = await effective_assignment(session, org_id, agent.owner_user_id)
    return Target(found.connection_id, found.model) if found is not None else None


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
    owner's AI and the organisation's switch; its connection is the owner's."""
    target = await run_target(session, org_id, agent)
    if target is None:
        return Refusal.AI_UNAVAILABLE
    if agent.owner_user_id is not None and not await personal_agents_allowed(session, org_id):
        return Refusal.PERSONAL_DISABLED
    standing = await AgentRepository(session, org_id).standing(
        agent, target.connection_id, target.model
    )
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
