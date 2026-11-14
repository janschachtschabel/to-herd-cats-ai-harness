"""The actor a run reads with (spec 5.6; plan M5 decision 3), and the checks the run
repeats before every model call and every tool call.

A run acts as the person who asked, held to what the agent itself may read: the
person's own principal, system role and groups, with `read_scope` set to the agent's
roles (its space memberships, and `viewer` in the open spaces) as far as the audience
of the run's place may see them, and `write_scope` to where that place lets it write
(`scope.py`, plan M6 decision 5). `core/access.py` applies both to whatever actor
carries them; nothing here or there treats agents specially. The actor is built anew
for every check, so a right the person or the agent lost in the meantime is lost for
the run too.
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
from app.modules.agents.scope import place_of, scopes
from app.modules.agents.standing import agent_refusal, owned_by
from app.modules.groups.repository import GroupRepository
from app.modules.users.repository import UserRepository


@dataclass(slots=True)
class Reads:
    """What the run has read so far: its policy and rights are checked against all of
    it before every model call (the conversation itself counts as policy `any`). The
    spaces as they were at read time, and the pages and tickets, whose spaces are
    looked up again for every check (a page moved since counts where it is now).
    `drafts`: the spaces of drafts it read, as they were then (journaled with the
    call that read them): only their editors may read what the run writes while it
    holds one (`toolbox/writing.carries_draft`, review M6 2 finding 1)."""

    spaces: set[uuid.UUID] = field(default_factory=set)
    pages: set[uuid.UUID] = field(default_factory=set)
    tickets: set[uuid.UUID] = field(default_factory=set)
    drafts: set[uuid.UUID] = field(default_factory=set)


async def run_actor(
    session: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
    conversation_id: uuid.UUID | None = None,
) -> Actor | None:
    """The run's actor as of now, for its conversation's place (without one: as in a
    DM alone with the agent); None once the person no longer acts or the conversation
    is gone."""
    user = await UserRepository(session).get_current(org_id, user_id)
    if user is None or not user.is_active:
        return None
    principal = Principal.user(user.id)
    groups = await GroupRepository(session).group_ids_for(principal)
    roles = await AgentRepository(session, org_id).roles(agent_id)
    if conversation_id is None:
        return Actor(org_id, principal, user.system_role, groups, ReadScope.of(roles))
    place = await place_of(session, org_id, conversation_id, user.id)
    if place is None:
        return None
    found = await scopes(session, org_id, place, roles)
    return Actor(org_id, principal, user.system_role, groups, found.read, found.write)


async def allowed_actor(
    session: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    agent: Agent,
    reads: Reads,
    conversation_id: uuid.UUID,
) -> Actor | None:
    """The run's actor if the run may go on (None: `rights_revoked`): the person acts
    and has `ai.use` (and owns the agent, if it is a personal one), the agent may run
    (`standing.agent_refusal`), and every space read so far, where it was read and
    where it is now, is still visible to the person and the agent together."""
    actor = await run_actor(session, org_id, user_id, agent.id, conversation_id)
    if actor is None or not owned_by(agent, actor) or not await can(session, actor, Action.AI_USE):
        return None
    if await agent_refusal(session, org_id, agent) is not None:
        return None
    repo = ReadRepository(session, org_id)
    spaces = reads.spaces | (await repo.now(reads)).spaces
    if spaces and await repo.still_visible(actor, spaces) != spaces:
        return None
    return actor
