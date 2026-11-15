"""The tickets' outbox events (spec 4.3), written in the transaction of the change, so
an event exists exactly when its change committed. One event per change:

- `ticket.created` (payload `ticket_id`, `conversation_id`: the ticket's thread;
  `fields`/`changes` name an assignee it was created with);
- `ticket.updated` (the same keys): `fields` names every field that changed, sorted;
  `changes` holds the old and new value for the fields with a value worth a timeline
  entry (`VALUED`): ids (status, assignee, parent, a page linked or unlinked) and
  enumeration values or dates. Tags are only named.
  A title or description change is only named, never carried (plan M4 Global
  Constraints): payloads hold ids and enumeration values, never text. A change an
  agent's run wrote also names the run (`run_id`, plan M6 task 6); the event's actor
  is then the agent.
- `sprint.created`, `sprint.updated`, `sprint.started`, `sprint.closed` (plan M4b;
  payload `sprint_id` and `fields`, the names of the fields that changed); subject:
  the sprint. Closing a sprint also writes one `ticket.updated` (field `sprint`) per
  ticket it moves.

Subject: the ticket; space: its space.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Acting, NewEvent, emit, emit_many

TICKET_CREATED = "ticket.created"
TICKET_UPDATED = "ticket.updated"
TICKET_EVENTS = (TICKET_CREATED, TICKET_UPDATED)
SPRINT_CREATED = "sprint.created"
SPRINT_UPDATED = "sprint.updated"
SPRINT_STARTED = "sprint.started"
SPRINT_CLOSED = "sprint.closed"
SPRINT_EVENTS = (SPRINT_CREATED, SPRINT_UPDATED, SPRINT_STARTED, SPRINT_CLOSED)


class Field(StrEnum):
    """The changeable fields, as events name them."""

    ASSIGNEE = "assignee"
    DESCRIPTION = "description"
    DUE_ON = "due_on"
    KIND = "kind"
    PAGE = "page"  # a page linked (from null to its id) or unlinked (from its id to null)
    PARENT = "parent"
    PRIORITY = "priority"
    SPRINT = "sprint"
    STATUS = "status"
    TAGS = "tags"
    TITLE = "title"


VALUED = frozenset(
    {
        Field.ASSIGNEE,
        Field.DUE_ON,
        Field.KIND,
        Field.PAGE,
        Field.PARENT,
        Field.PRIORITY,
        Field.SPRINT,
        Field.STATUS,
    }
)

Value = uuid.UUID | date | StrEnum | None
Changes = Mapping[Field, tuple[Value, Value]]  # field → (old, new)


def _text(value: Value) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def payload(
    ticket_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    changes: Changes,
    run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    found: dict[str, Any] = {
        "ticket_id": str(ticket_id),
        "conversation_id": str(conversation_id) if conversation_id else None,
        "fields": sorted(field.value for field in changes),
        "changes": {
            field.value: {"from": _text(old), "to": _text(new)}
            for field, (old, new) in sorted(changes.items())
            if field in VALUED
        },
    }
    if run_id is not None:
        found["run_id"] = str(run_id)
    return found


async def ticket_event(
    session: AsyncSession,
    actor: Acting,
    type_: str,
    *,
    ticket_id: uuid.UUID,
    space_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    changes: Changes,
    run_id: uuid.UUID | None = None,
) -> None:
    await emit(
        session,
        type=type_,
        actor=actor,
        space_id=space_id,
        subject_type="ticket",
        subject_id=ticket_id,
        payload=payload(ticket_id, conversation_id, changes, run_id),
    )


@dataclass(frozen=True, slots=True)
class TicketChange:
    """One ticket's change, for `ticket_events`."""

    ticket_id: uuid.UUID
    space_id: uuid.UUID
    conversation_id: uuid.UUID | None
    changes: Changes


async def ticket_events(
    session: AsyncSession, actor: Acting, type_: str, items: Sequence[TicketChange]
) -> None:
    """One event per ticket, written together (one INSERT, `emit_many`)."""
    await emit_many(
        session,
        actor=actor,
        events=[
            NewEvent(
                type_,
                item.space_id,
                "ticket",
                item.ticket_id,
                payload(item.ticket_id, item.conversation_id, item.changes),
            )
            for item in items
        ],
    )


async def sprint_event(
    session: AsyncSession,
    actor: Acting,
    type_: str,
    *,
    sprint_id: uuid.UUID,
    space_id: uuid.UUID,
    fields: list[str],
) -> None:
    await emit(
        session,
        type=type_,
        actor=actor,
        space_id=space_id,
        subject_type="sprint",
        subject_id=sprint_id,
        payload={"sprint_id": str(sprint_id), "fields": sorted(fields)},
    )
