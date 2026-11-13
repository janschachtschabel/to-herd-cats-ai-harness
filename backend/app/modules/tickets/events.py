"""The tickets' outbox events (spec 4.3), written in the transaction of the change, so
an event exists exactly when its change committed. One event per change:

- `ticket.created` (payload `ticket_id`, `conversation_id`: the ticket's thread;
  `fields`/`changes` name an assignee it was created with);
- `ticket.updated` (the same keys): `fields` names every field that changed, sorted;
  `changes` holds the old and new value for the fields with a value worth a timeline
  entry (`VALUED`): ids (status, assignee, parent, a page linked or unlinked) and
  enumeration values or dates. Tags are only named.
  A title or description change is only named, never carried (plan M4 Global
  Constraints): payloads hold ids and enumeration values, never text.

Subject: the ticket; space: its space.
"""

import uuid
from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Acting, emit

TICKET_CREATED = "ticket.created"
TICKET_UPDATED = "ticket.updated"
TICKET_EVENTS = (TICKET_CREATED, TICKET_UPDATED)


class Field(StrEnum):
    """The changeable fields, as events name them."""

    ASSIGNEE = "assignee"
    DESCRIPTION = "description"
    DUE_ON = "due_on"
    KIND = "kind"
    PAGE = "page"  # a page linked (from null to its id) or unlinked (from its id to null)
    PARENT = "parent"
    PRIORITY = "priority"
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
    ticket_id: uuid.UUID, conversation_id: uuid.UUID | None, changes: Changes
) -> dict[str, Any]:
    return {
        "ticket_id": str(ticket_id),
        "conversation_id": str(conversation_id) if conversation_id else None,
        "fields": sorted(field.value for field in changes),
        "changes": {
            field.value: {"from": _text(old), "to": _text(new)}
            for field, (old, new) in sorted(changes.items())
            if field in VALUED
        },
    }


async def ticket_event(
    session: AsyncSession,
    actor: Acting,
    type_: str,
    *,
    ticket_id: uuid.UUID,
    space_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    changes: Changes,
) -> None:
    await emit(
        session,
        type=type_,
        actor=actor,
        space_id=space_id,
        subject_type="ticket",
        subject_id=ticket_id,
        payload=payload(ticket_id, conversation_id, changes),
    )
