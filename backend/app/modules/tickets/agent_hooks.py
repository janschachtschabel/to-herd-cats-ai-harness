"""What tickets ask of agents, without importing the agents module (the pattern of
`messaging/agent_hooks.py`): agents build on tickets (their tools read and change
tickets), so tickets must not depend on agents. The agents module registers its
`AssigneeHooks` when `app.modules.agents.hooks` is imported (the API's routers and the
worker do). Without them no agent can be assigned (plan M6 decision 7).
"""

import uuid
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.authorship import Authorship
from app.modules.tickets.models import WorkItem


class AssigneeHooks(Protocol):
    async def assignable(
        self, session: AsyncSession, actor: Actor, space_id: uuid.UUID, agent_id: uuid.UUID
    ) -> bool:
        """Whether the actor may hand tickets of the space to the agent: the actor has
        `ai.use`, the agent is no draft and a member of the space with a role that lets
        it work on tickets there."""
        ...

    async def claimable(
        self, session: AsyncSession, actor: Actor, space_id: uuid.UUID, agent_id: uuid.UUID
    ) -> bool:
        """Whether the agent may take tickets of the space for itself (`claiming.py`):
        no draft, a member with a role that lets it work on tickets there."""
        ...

    async def assigned(
        self, session: AsyncSession, actor: Actor, ticket: WorkItem, by: Authorship | None
    ) -> None:
        """The ticket was just assigned to an agent (by `actor`, written for `by` when
        an agent's run did it): start the agent's run on it, or note why not
        (`agents/triggers.py`)."""
        ...

    async def unassigned(
        self,
        session: AsyncSession,
        actor: Actor,
        ticket: WorkItem,
        former: uuid.UUID,
        by: Authorship | None,
    ) -> None:
        """The ticket was just taken from `former` (to someone else or nobody): if it
        is an agent, ask its open runs on the ticket to stop, except the run that did
        it (`by`)."""
        ...


_registered: list[AssigneeHooks] = []


def register_assignee_hooks(hooks: AssigneeHooks) -> None:
    _registered[:] = [hooks]


def assignee_hooks() -> AssigneeHooks | None:
    return _registered[0] if _registered else None
