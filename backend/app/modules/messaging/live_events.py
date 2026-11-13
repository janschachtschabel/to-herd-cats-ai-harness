"""What travels from the worker to every API process for live delivery (spec 6.4).

The outbox handler `publish_live` turns an event into a `NOTIFY herd_live` in the
handler's transaction (sent when it commits). The payload is compact JSON with ids
only, never content:

    {"t": <SSE event name>, "o": <org_id>, "c": <conversation_id|null>,
     "m": <message_id|null>, "p": <parent_id|null>, "u": <user_id|null>}

`u` names the one person an event is for (`notification.created`,
`conversation.read`, `activity.changed`); without it, whoever may see conversation
`c` gets it. Every API process's hub (`live.py`) decodes it again; anything it cannot
use is dropped. Payloads stay far below Postgres' 8000-byte limit (about 230 bytes).
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event

LIVE_CHANNEL = "herd_live"
MAX_PAYLOAD_BYTES = 4000

# Outbox event type → SSE event name. Channel changes of every kind are one event.
LIVE_TYPES: dict[str, str] = {
    "message.created": "message.created",
    "message.updated": "message.updated",
    "message.deleted": "message.deleted",
    "reaction.changed": "reaction.changed",
    "notification.created": "notification.created",
    "conversation.read": "conversation.read",
    "activity.changed": "activity.changed",
    "channel.created": "channel.changed",
    "channel.updated": "channel.changed",
    "channel.archived": "channel.changed",
    "channel.unarchived": "channel.changed",
}
LIVE_NAMES = frozenset(LIVE_TYPES.values())
# Events for one person: the payload's `user_id` is who gets them.
FOR_ONE_PERSON = frozenset({"notification.created", "conversation.read", "activity.changed"})


@dataclass(frozen=True, slots=True)
class LiveEvent:
    name: str
    org_id: uuid.UUID
    conversation_id: uuid.UUID | None
    message_id: uuid.UUID | None
    parent_id: uuid.UUID | None
    user_id: uuid.UUID | None

    def payload(self) -> str:
        return json.dumps(
            {
                "t": self.name,
                "o": str(self.org_id),
                "c": _text(self.conversation_id),
                "m": _text(self.message_id),
                "p": _text(self.parent_id),
                "u": _text(self.user_id),
            },
            separators=(",", ":"),
        )

    def frame(self) -> bytes:
        """The server-sent event: its name and the ids a client reloads by."""
        data = {
            "conversation_id": _text(self.conversation_id),
            "message_id": _text(self.message_id),
            "parent_id": _text(self.parent_id),
        }
        return sse_frame(self.name, data)


def sse_frame(name: str, data: dict[str, Any]) -> bytes:
    return f"event: {name}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n".encode()


def _text(value: uuid.UUID | None) -> str | None:
    return None if value is None else str(value)


def of_event(event: Event) -> LiveEvent | None:
    """The live event of an outbox event; None for types that are not delivered live."""
    name = LIVE_TYPES.get(event.type)
    if name is None:
        return None
    payload = event.payload
    return LiveEvent(
        name=name,
        org_id=event.org_id,
        conversation_id=_uuid(payload.get("conversation_id")),
        message_id=_uuid(payload.get("message_id")),
        parent_id=_uuid(payload.get("parent_id")),
        user_id=_uuid(payload.get("user_id")) if event.type in FOR_ONE_PERSON else None,
    )


def _uuid(value: object) -> uuid.UUID | None:
    return uuid.UUID(value) if isinstance(value, str) else None


async def publish_live(session: AsyncSession, event: Event) -> None:
    """Outbox handler: NOTIFY every API process. A second delivery notifies again,
    which costs a client one reload of what it shows, nothing more."""
    live = of_event(event)
    if live is None:
        return
    payload = live.payload()
    if len(payload.encode()) > MAX_PAYLOAD_BYTES:  # ids only: cannot happen
        raise ValueError("live payload too large")
    await session.execute(select(func.pg_notify(LIVE_CHANNEL, payload)))


def decode(raw: str) -> LiveEvent | None:
    """The event in a NOTIFY payload; None for anything else."""
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("t") not in LIVE_NAMES:
            return None
        ids = {key: _strict_uuid(data.get(key)) for key in ("c", "m", "p", "u")}
        org_id = _strict_uuid(data.get("o"))
    except (ValueError, TypeError, RecursionError):
        return None
    if org_id is None:
        return None
    return LiveEvent(data["t"], org_id, ids["c"], ids["m"], ids["p"], ids["u"])


def _strict_uuid(value: object) -> uuid.UUID | None:
    """None for null; a UUID for its text; anything else is refused (ValueError)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("not an id")
    return uuid.UUID(value)
