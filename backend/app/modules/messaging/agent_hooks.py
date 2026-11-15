"""What messaging asks of agents, without importing the agents module (plan M5 task
5; the same pattern as `ticket_hooks.py`).

Agents build on messaging (an agent takes part in a DM, posts its answer there), so
messaging must not depend on agents. The agents module registers its `AgentHooks`
when `app.modules.agents.hooks` is imported (the API's routers and the worker do);
messaging asks through `agent_hooks()`.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.modules.messaging.models import Conversation, Message


@dataclass(frozen=True, slots=True)
class RunStart:
    """What a message in a DM with an agent, or one that mentions an agent, started: a
    run (`run_id`, possibly one already waiting that answers it too), or none and why
    (`reason`, a code the client words: `ai.unavailable`, `agent.paused`, ...).
    `agent_id`: the agent it asked (one a mention named is not "not notified")."""

    run_id: uuid.UUID | None
    reason: str | None
    agent_id: uuid.UUID | None = None


class AgentHooks(Protocol):
    async def require_addressable(
        self, session: AsyncSession, actor: Actor, agent_id: uuid.UUID
    ) -> None:
        """Raise 404 `agent.not_found` unless the actor may open a DM with the agent."""
        ...

    async def after_post(
        self,
        session: AsyncSession,
        actor: Actor,
        conversation: Conversation,
        message: Message,
        mentioned: list[uuid.UUID],
    ) -> RunStart | None:
        """For a person's new message: in a DM, the run it starts or why none (None:
        the DM has no agent); elsewhere, the run a mention of an agent among
        `mentioned` starts or why none (None: it mentions no agent it may ask)."""
        ...

    async def names(
        self, session: AsyncSession, org_id: uuid.UUID, ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """The names of the agents with these ids."""
        ...

    async def external_ids(
        self, session: AsyncSession, org_id: uuid.UUID, ids: Iterable[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Those of these ids that are external agents (plan M8 decision 11)."""
        ...


_registered: list[AgentHooks] = []


def register_agent_hooks(hooks: AgentHooks) -> None:
    _registered[:] = [hooks]


def agent_hooks() -> AgentHooks:
    if not _registered:
        raise RuntimeError("no agent hooks: import app.modules.agents.hooks first")
    return _registered[0]
