"""The outbox handlers of proposals (plan M6 task 5), registered by name (stored with
each delivery, metric labels); the worker imports this module (`app/worker/handlers.py`).

- `proposal_timeline`: one system message per proposal event in the thread of the page
  it is about (a change: its page; a new page: its parent; a new page at the top level
  has no thread and gets none). The body is a key and the actor's id
  (`{"key": "proposal.created", "actor": "<id>"}`), never a title, a reason or content;
  it refers to its event (`client_id`), so a second delivery writes nothing; each new
  one is emitted (`message.created`, flagged `system`) for live delivery and notifies
  nobody by itself.
- `notify_on_proposal`: `proposal` notifications pointing at that entry: on
  `proposal.created` for the space's moderators (by membership, `repository.moderators`)
  other than its author; on `proposal.accepted|rejected` for its author when that is a
  person other than whoever decided. Only for people who may see the page's thread when
  the handler runs. The entry is written here if the timeline handler has not run yet
  (the two run in any order). A new page at the top level has no thread: its
  notifications (for the moderators, who hold `page.moderate` there now) name the
  proposal and its space instead (seen by the space's page editors, plan M6 task 6).
  A withdrawal notifies nobody.

The actor of a proposal made or withdrawn is its author (an agent), so the entry and
the activity name the agent (`events.py`).
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, emit
from app.core.principal import PrincipalType
from app.modules.messaging.models import Message
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.notification_repository import NotificationRepository
from app.modules.messaging.notifications import announce
from app.modules.messaging.repository import readers_of
from app.modules.messaging.thread_repository import PageThreadRepository
from app.modules.proposals.events import (
    PROPOSAL_ACCEPTED,
    PROPOSAL_CREATED,
    PROPOSAL_EVENTS,
    PROPOSAL_REJECTED,
)
from app.modules.proposals.repository import ProposalFacts
from app.modules.tokens.marks import via_token
from app.worker.registry import handler


async def write_entry(session: AsyncSession, event: Event) -> Message | None:
    """The event's timeline entry, written unless it exists; None when there is no
    page to tell (the top level, or a page purged meanwhile)."""
    if event.subject_type != "proposal" or event.type not in PROPOSAL_EVENTS:
        return None
    page_id = event.payload.get("page_id")
    if not isinstance(page_id, str):
        return None
    repo = PageThreadRepository(session, event.org_id)
    page = await repo.page(uuid.UUID(page_id))
    if page is None:
        return None
    thread = await repo.thread_for(page)
    body = json.dumps({"key": event.type, "actor": str(event.actor.id)})
    marked = await via_token(session, event)
    message = await repo.add_system(thread, event.id, body, event.created_at, via_token=marked)
    if message is None:
        return await repo.system_message(event.id)
    await emit(
        session,
        type="message.created",
        actor=event.acting,
        space_id=page.space_id,
        subject_type="message",
        subject_id=message.id,
        payload={
            "conversation_id": str(thread.id),
            "message_id": str(message.id),
            "parent_id": None,
            "system": True,
        },
    )
    return message


async def proposal_timeline(session: AsyncSession, event: Event) -> None:
    await write_entry(session, event)


async def notify_on_proposal(session: AsyncSession, event: Event) -> None:
    if event.type not in (PROPOSAL_CREATED, PROPOSAL_ACCEPTED, PROPOSAL_REJECTED):
        return
    proposal = await ProposalFacts(session, event.org_id).proposal(event.subject_id)
    if proposal is None:
        return
    person = proposal.author_id if proposal.author_type == PrincipalType.USER else None
    facts = ProposalFacts(session, event.org_id)
    if event.type == PROPOSAL_CREATED:
        wanted = {u for u in await facts.moderators(proposal.space_id) if u != person}
    else:
        wanted = {person} if person is not None and person != event.actor.id else set()
    if not wanted:
        return
    repo = NotificationRepository(session, event.org_id)
    if event.payload.get("page_id") is None:  # a new page at the top level: no thread
        rows = [(u, NotificationReason.PROPOSAL) for u in sorted(wanted)]
        for notification in await repo.add_for_proposal(proposal.id, proposal.space_id, rows):
            await announce(session, event, notification)
        return
    entry = await write_entry(session, event)
    if entry is None or entry.conversation_id is None:
        return
    readers = await readers_of(session, event.org_id, entry.conversation_id, wanted)
    rows = [(u, NotificationReason.PROPOSAL) for u in sorted(readers)]
    for notification in await repo.add(entry, rows):
        await announce(session, event, notification)


handler(PROPOSAL_EVENTS, "proposal_timeline")(proposal_timeline)
handler(PROPOSAL_EVENTS, "notify_on_proposal")(notify_on_proposal)
