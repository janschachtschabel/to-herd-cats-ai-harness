"""The actor a run reads with (spec 5.6; plan M5 decision 3), and the checks the run
repeats before every model call and every tool call.

A run acts as the person who asked, held to what the agent itself may read: the
person's own principal, system role and groups, with `read_scope` set to the agent's
roles (its space memberships, and `viewer` in the open spaces). `core/access.py`
applies the scope to whatever actor carries it; nothing here or there treats agents
specially. The actor is built anew for every check, so a right the person or the agent
lost in the meantime is lost for the run too.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.actor import ReadScope
from app.core.principal import Principal
from app.modules.agents.models import Agent
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.repository import AgentRepository
from app.modules.agents.standing import agent_refusal
from app.modules.groups.repository import GroupRepository
from app.modules.users.repository import UserRepository


@dataclass(slots=True)
class Reads:
    """What the run has read so far: its policy and rights are checked against all of
    it before every model call (the conversation itself counts as policy `any`). The
    spaces as they were at read time, and the pages and tickets, whose spaces are
    looked up again for every check (a page moved since counts where it is now)."""

    spaces: set[uuid.UUID] = field(default_factory=set)
    pages: set[uuid.UUID] = field(default_factory=set)
    tickets: set[uuid.UUID] = field(default_factory=set)


async def run_actor(
    session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, agent_id: uuid.UUID
) -> Actor | None:
    """The run's actor as of now; None once the person no longer acts."""
    user = await UserRepository(session).get_current(org_id, user_id)
    if user is None or not user.is_active:
        return None
    principal = Principal.user(user.id)
    groups = await GroupRepository(session).group_ids_for(principal)
    roles = await AgentRepository(session, org_id).roles(agent_id)
    return Actor(org_id, principal, user.system_role, groups, ReadScope.of(roles))


async def allowed_actor(
    session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, agent: Agent, reads: Reads
) -> Actor | None:
    """The run's actor if the run may go on (None: `rights_revoked`): the person acts
    and has `ai.use`, the agent may run (`standing.agent_refusal`), and every space read
    so far, where it was read and where it is now, is still visible to the person and
    the agent together."""
    actor = await run_actor(session, org_id, user_id, agent.id)
    if actor is None or not await can(session, actor, Action.AI_USE):
        return None
    if await agent_refusal(session, org_id, agent) is not None:
        return None
    repo = ReadRepository(session, org_id)
    spaces = reads.spaces | (await repo.now(reads)).spaces
    if spaces and await repo.still_visible(actor, spaces) != spaces:
        return None
    return actor
