"""The outbox handlers of tickets (spec 6.2, plan M4 decision 10), registered by name
(stored with each delivery, metric labels); the worker imports this module
(`app/worker/handlers.py`).

- `ticket_timeline`: the ticket's thread gets one system message per change an event
  names, in a fixed order (created, status, assignee, priority, kind, parent, due
  date, title, description, a page linked or unlinked; tags get none). The body is a
  key with parameters for the client to word
  (`{"key": "ticket.status_changed", "actor": "<id>", "from": "<id>", "to": "<id>"}`):
  ids, enumeration values and dates, never a title or a description. Each entry
  refers to the event and its own name (`client_id`), so a second delivery writes
  nothing; each new one is emitted (`message.created`, flagged `system`) for live
  delivery and notifies nobody (`notify_on_message` skips system messages).
- `notify_on_ticket`: `assignment` for the person a ticket was assigned to, unless
  they assigned it themselves, and only if they may see the ticket when the handler
  runs. It points at the timeline's assignment entry, written here if the timeline
  handler has not run yet (the two run in any order).
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, emit
from app.modules.messaging.models import Message
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.notification_repository import NotificationRepository
from app.modules.messaging.notifications import announce
from app.modules.messaging.repository import readers_of
from app.modules.tickets.events import TICKET_CREATED, TICKET_EVENTS, Field
from app.modules.tickets.thread_repository import TicketThreadRepository
from app.worker.registry import handler

ORDER = (
    Field.STATUS,
    Field.ASSIGNEE,
    Field.PRIORITY,
    Field.KIND,
    Field.PARENT,
    Field.SPRINT,
    Field.DUE_ON,
    Field.TITLE,
    Field.DESCRIPTION,
    Field.PAGE,
)
KEYS = {
    Field.STATUS: "ticket.status_changed",
    Field.PRIORITY: "ticket.priority_changed",
    Field.KIND: "ticket.kind_changed",
    Field.PARENT: "ticket.parent_changed",
    Field.SPRINT: "ticket.sprint_changed",
    Field.DUE_ON: "ticket.due_changed",
    Field.TITLE: "ticket.title_changed",
    Field.DESCRIPTION: "ticket.description_changed",
}
# Fields whose entry says whether something was set or taken away.
TOGGLED = {
    Field.ASSIGNEE: ("ticket.assigned", "ticket.unassigned"),
    Field.PAGE: ("ticket.page_linked", "ticket.page_unlinked"),
}
CREATED = "created"  # the name of a creation's own entry


def entries(event: Event) -> list[tuple[str, dict[str, object]]]:
    """The timeline entries of a ticket event: (name, body), in their order. A change an
    agent's run wrote names the agent as `actor` and the run (`run_id`)."""
    actor = str(event.actor.id)
    run_id = event.payload.get("run_id")
    found: list[tuple[str, dict[str, object]]] = []
    if event.type == TICKET_CREATED:
        found.append((CREATED, {"key": "ticket.created", "actor": actor}))
    fields = set(event.payload.get("fields") or [])
    changes = event.payload.get("changes") or {}
    for field in ORDER:
        if field.value not in fields:
            continue
        body: dict[str, object] = {"key": KEYS.get(field, ""), "actor": actor}
        change = changes.get(field.value)
        if isinstance(change, dict):
            body["from"], body["to"] = change.get("from"), change.get("to")
        if field in TOGGLED:
            on, off = TOGGLED[field]
            body["key"] = on if body.get("to") else off
            if not body.get("to"):
                body.pop("to", None)
        found.append((field.value, body))
    if isinstance(run_id, str):
        for _, body in found:
            body["run_id"] = run_id
    return found


async def write_timeline(session: AsyncSession, event: Event) -> dict[str, Message]:
    """The event's timeline entries by name, written unless they exist; empty when
    the ticket is gone."""
    if event.subject_type != "ticket" or event.type not in TICKET_EVENTS:
        return {}
    repo = TicketThreadRepository(session, event.org_id)
    found = await repo.ticket_and_thread(event.subject_id)
    if found is None:
        return {}
    ticket, thread = found
    written: dict[str, Message] = {}
    for offset, (name, body) in enumerate(entries(event)):
        client_id = uuid.uuid5(event.id, name)
        message = await repo.add_system(
            thread, client_id, json.dumps(body), event.created_at, offset
        )
        if message is not None:
            await emit(
                session,
                type="message.created",
                actor=event.acting,
                space_id=ticket.space_id,
                subject_type="message",
                subject_id=message.id,
                payload={
                    "conversation_id": str(thread.id),
                    "message_id": str(message.id),
                    "parent_id": None,
                    "system": True,
                },
            )
        else:
            message = await repo.system_message(client_id)
        if message is not None:
            written[name] = message
    return written


async def ticket_timeline(session: AsyncSession, event: Event) -> None:
    await write_timeline(session, event)


async def notify_on_ticket(session: AsyncSession, event: Event) -> None:
    change = (event.payload.get("changes") or {}).get(Field.ASSIGNEE.value)
    to = change.get("to") if isinstance(change, dict) else None
    if not to or uuid.UUID(to) == event.actor.id:
        return
    entry = (await write_timeline(session, event)).get(Field.ASSIGNEE.value)
    if entry is None:
        return
    assignee = uuid.UUID(to)
    if assignee not in await readers_of(session, event.org_id, entry.conversation_id, [assignee]):
        return
    repo = NotificationRepository(session, event.org_id)
    for notification in await repo.add(entry, [(assignee, NotificationReason.ASSIGNMENT)]):
        await announce(session, event, notification)


handler(TICKET_EVENTS, "ticket_timeline")(ticket_timeline)
handler(TICKET_EVENTS, "notify_on_ticket")(notify_on_ticket)
