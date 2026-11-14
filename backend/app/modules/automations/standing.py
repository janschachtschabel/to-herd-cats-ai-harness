"""Who may own an automation, and whether its place lets it run now (plan M7
decisions 2, 3, 6, 12 and 13).

**Owning** (`may_own`): a person may own an automation (make it, take it over, keep
it) while they have `ai.use`, reach its agent (not a draft; a personal agent only
its owner) and may write at its place:

- the person's DM with the agent (the two of them alone);
- a channel or a ticket's thread of a space where the person may post
  (`channel.post`; a ticket's thread also needs `ticket.read`) and the agent is a
  member (a personal agent is a member only of its owner's personal space).

The due loop asks it of the owner at every term (`owner_may_run`): a deactivated
owner, or one who lost any of it, pauses the automation (`paused_reason = owner`); it
never runs with rights its owner no longer has, and rights never move to someone
else without an explicit take-over (`takeover.py`).

**The place** (`place_closed`): an archived conversation, or a space whose AI policy
keeps its content from the connection the agent uses now (`none`, or `restricted`
without its data location), skips the term (`skipped_policy`); the automation keeps
its terms, and runs again once the place is open.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, actor_for, can
from app.core.errors import NotFound
from app.modules.agents.models import Agent, AgentStatus
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.repository import AgentRepository
from app.modules.agents.scope_repository import ScopeRepository
from app.modules.agents.standing import owned_by
from app.modules.ai.models import AiConnection
from app.modules.ai.policy import ANY, connection_allowed, strictest
from app.modules.auth.context import AuthContext
from app.modules.messaging.models import Conversation, ConversationKind
from app.modules.messaging.visibility import ConversationReader
from app.modules.users.repository import UserRepository

PLACES = frozenset({ConversationKind.DM, ConversationKind.CHANNEL, ConversationKind.THREAD_TICKET})


async def person(session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> Actor | None:
    """The person as the checks see them now (None: gone or deactivated)."""
    user = await UserRepository(session).get_current(org_id, user_id)
    if user is None or not user.is_active:
        return None
    return await actor_for(session, AuthContext(user=user))


async def may_own(
    session: AsyncSession, actor: Actor, agent: Agent, conversation: Conversation
) -> bool:
    if conversation.kind not in PLACES or conversation.org_id != actor.org_id:
        return False
    if not await can(session, actor, Action.AI_USE):
        return False
    if agent.status == AgentStatus.DRAFT or not owned_by(agent, actor):
        return False
    if conversation.kind == ConversationKind.DM:
        return await _alone_with(session, actor, agent, conversation)
    assert conversation.space_id is not None  # a channel's or a ticket thread's
    try:
        await ConversationReader(session).readable(actor, conversation.id)
    except NotFound:
        return False
    if not await can(session, actor, Action.CHANNEL_POST, conversation.space_id):
        return False
    members = await AgentRepository(session, actor.org_id).member_space_ids(agent.id)
    return conversation.space_id in members


async def owner_may_run(
    session: AsyncSession,
    owner_id: uuid.UUID,
    agent: Agent,
    conversation: Conversation,
) -> bool:
    actor = await person(session, agent.org_id, owner_id)
    return actor is not None and await may_own(session, actor, agent, conversation)


async def _alone_with(
    session: AsyncSession, actor: Actor, agent: Agent, conversation: Conversation
) -> bool:
    """The person's DM with the agent, the two of them alone."""
    talking = await AgentRepository(session, actor.org_id).of_conversation(conversation.id)
    if talking is None or talking.id != agent.id:
        return False
    people = await ScopeRepository(session, actor.org_id).people(conversation.id)
    return people == {actor.principal.id}


async def place_closed(
    session: AsyncSession, conversation: Conversation, connection: AiConnection | None
) -> bool:
    """Whether the place keeps the run out now: archived, or (in a space) closed to
    the connection by the space's AI policy."""
    if conversation.archived_at is not None or connection is None:
        return True
    if conversation.space_id is None:
        return False
    policies = await ReadRepository(session, conversation.org_id).policies({conversation.space_id})
    return not connection_allowed(connection, strictest([ANY, *policies]))
