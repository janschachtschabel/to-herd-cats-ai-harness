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


class AssigneeHooks(Protocol):
    async def assignable(
        self, session: AsyncSession, actor: Actor, space_id: uuid.UUID, agent_id: uuid.UUID
    ) -> bool:
        """Whether the actor may hand tickets of the space to the agent: the actor has
        `ai.use`, the agent is no draft and a member of the space with a role that lets
        it work on tickets there."""
        ...


_registered: list[AssigneeHooks] = []


def register_assignee_hooks(hooks: AssigneeHooks) -> None:
    _registered[:] = [hooks]


def assignee_hooks() -> AssigneeHooks | None:
    return _registered[0] if _registered else None
