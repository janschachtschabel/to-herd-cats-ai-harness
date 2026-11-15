"""Who may make an automation, and where (plan M7 decisions 3 and 12): the place as the
API names it, found for the person who will own it, and the rules for making one
there. The same rules hold when its owner changes it (`service.update`).

- The agent: one the person may address (`ai.use`, not a draft, a personal agent only
  its owner's; else 404 `agent.not_found`).
- The place: the person's DM with the agent (opened if new); a channel the person
  sees (404 `conversation.not_found`); a ticket's thread by the ticket's number
  (404 `ticket.not_found`; the thread is opened if the ticket has none yet).
- In a channel or a ticket's thread the agent must be a member of the space (422
  `automation.agent_not_member`; a personal agent is one only of its owner's personal
  space). Then `standing.may_own`: the person may post there, and for an event rule
  manage the space (`space.manage`) (403 `automation.not_allowed`).
- An event rule needs a channel or a ticket's thread (422 `automation.invalid_place`);
  a tag filter names a system tag or one of that space (422
  `automation.invalid_filter`).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import Forbidden, ValidationFailed
from app.modules.agents.models import Agent
from app.modules.agents.repository import AgentRepository
from app.modules.automations.manage_repository import ManageRepository
from app.modules.automations.models import AutomationKind
from app.modules.automations.schedule import Planned
from app.modules.automations.schemas import ChannelPlaceIn, DmPlaceIn, TicketPlaceIn
from app.modules.automations.standing import may_own
from app.modules.messaging.dms import DmService
from app.modules.messaging.models import Conversation, ConversationKind
from app.modules.messaging.visibility import ConversationReader, conversation_not_found
from app.modules.tickets.base import readable, ticket_repository
from app.modules.tickets.thread_repository import TicketThreadRepository

PlaceIn = DmPlaceIn | ChannelPlaceIn | TicketPlaceIn


async def find(session: AsyncSession, actor: Actor, agent: Agent, place: PlaceIn) -> Conversation:
    """The conversation the place names, as the person may see it."""
    if isinstance(place, DmPlaceIn):
        return (await DmService(session).open(actor, [], agent_id=agent.id)).conversation
    if isinstance(place, ChannelPlaceIn):
        conversation = await ConversationReader(session).readable(actor, place.conversation_id)
        if conversation.kind != ConversationKind.CHANNEL:
            raise conversation_not_found()
        return conversation
    repo = ticket_repository(session, actor)
    ticket = await readable(session, actor, repo, place.ticket_number)
    return await TicketThreadRepository(session, actor.org_id).thread_for(ticket)


async def check(
    session: AsyncSession,
    actor: Actor,
    agent: Agent,
    place: Conversation,
    planned: Planned,
) -> None:
    """The person may own an automation of this kind of the agent at the place."""
    in_space = place.kind != ConversationKind.DM
    if planned.kind == AutomationKind.EVENT and not in_space:
        raise ValidationFailed(code="automation.invalid_place")
    if in_space:
        assert place.space_id is not None
        members = await AgentRepository(session, actor.org_id).member_space_ids(agent.id)
        if place.space_id not in members:
            raise ValidationFailed(code="automation.agent_not_member")
    if not await may_own(session, actor, agent, place, planned.kind):
        raise Forbidden(code="automation.not_allowed")
    if planned.kind != AutomationKind.EVENT:
        return
    assert place.space_id is not None
    tag_id: uuid.UUID | None = planned.columns["filter_tag_id"]
    repo = ManageRepository(session, actor.org_id)
    if tag_id is not None and not await repo.tag_fits(tag_id, place.space_id):
        raise ValidationFailed(code="automation.invalid_filter")
