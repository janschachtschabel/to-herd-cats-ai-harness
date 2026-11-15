"""Whether an event rule's run may be told of an event (plan M7 decision 8): only of
an object it could read itself, with the run's own scope at the rule's place (its
owner's rights ∩ the agent's ∩ the place's audience: in a channel or a ticket's
thread of the space, what a viewer of the space may see, `agents/scope.py`), by the
rules its tools read by (`PageReader.for_ai`: no drafts there, no page locked for AI,
no space closed to AI; an attachment locked for AI is not told either; a ticket in a
space whose tickets the run may read). An event about anything else is not taken in
at all: no run, no count, nothing in the log, so nothing of it reaches the place.

Whoever caused the event plays no part: the run is its owner's, at its place.

Where the place itself is closed to the run (archived, its space's AI policy) or the
owner may no longer run the rule, the term's own checks decide (`term.fire`:
`skipped_policy`, a pause), whatever the object.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, space_ids_with
from app.core.errors import NotFound
from app.core.outbox import Event
from app.modules.agents.actor import run_actor
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.repository import AgentRepository
from app.modules.agents.standing import run_target
from app.modules.ai.models import AiConnection
from app.modules.ai.policy_filters import ai_space_ids
from app.modules.automations.models import Automation, EventType
from app.modules.automations.repository import AutomationRepository
from app.modules.automations.standing import place_closed
from app.modules.spaces.models import Space
from app.modules.tickets.repository import TicketRepository, TicketScope
from app.modules.wiki.attachments_repository import AttachmentRepository
from app.modules.wiki.visibility import PageReader


async def may_tell(session: AsyncSession, rule: Automation, event: Event) -> bool:
    automations = AutomationRepository(session, rule.org_id)
    place = await automations.place(rule)
    agent = await AgentRepository(session, rule.org_id).get(rule.agent_id)
    assert agent is not None  # the rule goes with its agent
    actor = await run_actor(session, rule.org_id, rule.owner_user_id, agent.id, place.id)
    if actor is None:
        return True  # the term pauses the rule (`term.fire`)
    target = await run_target(session, rule.org_id, agent)
    connection = await session.get(AiConnection, target.connection_id) if target else None
    if await place_closed(session, place, connection):
        return True  # the term logs `skipped_policy`
    return await _readable(session, actor, event)


async def _readable(session: AsyncSession, actor: Actor, event: Event) -> bool:
    ids = event.payload
    try:
        if event.type == EventType.TICKET_CREATED:
            return await _ticket(session, actor, uuid.UUID(ids["ticket_id"]))
        reader = PageReader(session)
        if event.type == EventType.ATTACHMENT_UPLOADED:
            repo = AttachmentRepository(session, reader.scope(actor))
            attachment = await repo.get(uuid.UUID(ids["attachment_id"]))
            if attachment is None or attachment.no_ai:
                return False
        await reader.for_ai(actor, uuid.UUID(ids["page_id"]))
    except NotFound:
        return False
    return True


async def _ticket(session: AsyncSession, actor: Actor, ticket_id: uuid.UUID) -> bool:
    number = await ReadRepository(session, actor.org_id).ticket_number(ticket_id)
    if number is None:
        return False
    spaces = space_ids_with(actor, Action.TICKET_READ).where(
        Space.id.in_(ai_space_ids(actor.org_id))
    )
    repo = TicketRepository(session, TicketScope(actor.org_id, spaces))
    return await repo.by_number(number) is not None
