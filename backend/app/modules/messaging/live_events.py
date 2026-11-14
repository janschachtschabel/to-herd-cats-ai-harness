"""What travels from the worker to every API process for live delivery (spec 6.4).

The outbox handler `publish_live` turns an event into a `NOTIFY herd_live` in the
handler's transaction (sent when it commits). The payload is compact JSON with ids
only, never content:

    {"t": <SSE event name>, "o": <org_id>, "c": <conversation_id|null>,
     "m": <message_id|null>, "p": <parent_id|null>, "u": <user_id|null>,
     "w": <ticket_id>, "s": <space_id> (ticket events only),
     "r": <sprint_id> (sprint events only, with "s"),
     "x": <proposal_id> (proposal events only, with "s"),
     "n": <run_id>, "k": <step> (`run.progress` only)}

`u` names the one person an event is for (`notification.created`,
`conversation.read`, `activity.changed`, `access.changed`); without it, whoever may
see conversation `c` gets it (`dm.inspected`: a DM's participants, not the inspecting
administrator). Ticket events (`ticket.created`, `ticket.updated`) name the ticket's
thread as `c`, so whoever may see the thread, that is whoever may read tickets in the
ticket's space, gets them, the ticket as `w` and its space as `s` (a client refreshes
that ticket and that space's lists only, review M4 P4). Sprint events
(`sprint.created|updated|started|closed`, plan M4b) are one `sprint.changed` for the
space `s`: whoever may read tickets there gets it, with the space's and the sprint's
id (and nothing else). Proposal events (`proposal.created|accepted|rejected|
withdrawn`, plan M6 task 5) are one `proposal.changed` for the space `s`, for whoever
may edit pages there (who sees proposals), with the proposal's id. `run.progress`
(plan M5 task 6) names an agent's run in a DM
as `n` and its steps so far as `k`, for whoever may see the DM `c` (its person).
Every API process's hub
(`live.py`) decodes it again; anything it cannot use is dropped. Payloads stay far
below Postgres' 8000-byte limit (about 330 bytes).
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event
from app.core.permissions import Action

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
    "access.changed": "access.changed",
    "dm.inspected": "dm.inspected",
    "ticket.created": "ticket.created",
    "ticket.updated": "ticket.updated",
    "sprint.created": "sprint.changed",
    "sprint.updated": "sprint.changed",
    "sprint.started": "sprint.changed",
    "sprint.closed": "sprint.changed",
    "run.progress": "run.progress",
    "proposal.created": "proposal.changed",
    "proposal.accepted": "proposal.changed",
    "proposal.rejected": "proposal.changed",
    "proposal.withdrawn": "proposal.changed",
}
LIVE_NAMES = frozenset(LIVE_TYPES.values())
TICKET_TYPES = frozenset({"ticket.created", "ticket.updated"})
# Events for a space (no conversation, no person): sprints for whoever may read tickets
# there, proposals for whoever may edit pages there (`LiveEvent.space_action`).
SPRINT_TYPES = frozenset({"sprint.created", "sprint.updated", "sprint.started", "sprint.closed"})
PROPOSAL_TYPES = frozenset(t for t, name in LIVE_TYPES.items() if name == "proposal.changed")
SPACE_TYPES = SPRINT_TYPES | PROPOSAL_TYPES
# Events for one person: the payload's `user_id` is who gets them.
FOR_ONE_PERSON = frozenset(
    {"notification.created", "conversation.read", "activity.changed", "access.changed"}
)


@dataclass(frozen=True, slots=True)
class LiveEvent:
    name: str
    org_id: uuid.UUID
    conversation_id: uuid.UUID | None
    message_id: uuid.UUID | None
    parent_id: uuid.UUID | None
    user_id: uuid.UUID | None
    ticket_id: uuid.UUID | None = None
    space_id: uuid.UUID | None = None  # ticket, sprint and proposal events only
    sprint_id: uuid.UUID | None = None  # sprint events only
    run_id: uuid.UUID | None = None  # run.progress only, with `step`
    step: int | None = None
    proposal_id: uuid.UUID | None = None  # proposal events only

    @property
    def for_space(self) -> bool:
        """For people of the space (`space_action`): neither a conversation nor a
        person."""
        return self.conversation_id is None and self.user_id is None and self.space_id is not None

    @property
    def space_action(self) -> Action:
        """What a space event's recipients may do in the space."""
        return Action.PAGE_EDIT if self.name == "proposal.changed" else Action.TICKET_READ

    def payload(self) -> str:
        data: dict[str, object] = {
            "t": self.name,
            "o": str(self.org_id),
            "c": _text(self.conversation_id),
            "m": _text(self.message_id),
            "p": _text(self.parent_id),
            "u": _text(self.user_id),
        }
        if self.ticket_id is not None:
            data["w"] = str(self.ticket_id)
        if self.space_id is not None:
            data["s"] = str(self.space_id)
        if self.sprint_id is not None:
            data["r"] = str(self.sprint_id)
        if self.run_id is not None:
            data["n"] = str(self.run_id)
            data["k"] = self.step
        if self.proposal_id is not None:
            data["x"] = str(self.proposal_id)
        return json.dumps(data, separators=(",", ":"))

    def frame(self) -> bytes:
        """The server-sent event: its name and the ids a client reloads by (a ticket
        event also `ticket_id` and `space_id`; a sprint event only `space_id` and
        `sprint_id`; a proposal event only `space_id` and `proposal_id`)."""
        if self.for_space and self.name == "proposal.changed":
            return sse_frame(
                self.name, {"space_id": str(self.space_id), "proposal_id": _text(self.proposal_id)}
            )
        if self.for_space:
            return sse_frame(
                self.name, {"space_id": str(self.space_id), "sprint_id": _text(self.sprint_id)}
            )
        data: dict[str, object] = {
            "conversation_id": _text(self.conversation_id),
            "message_id": _text(self.message_id),
            "parent_id": _text(self.parent_id),
        }
        if self.ticket_id is not None:
            data["ticket_id"] = str(self.ticket_id)
        if self.space_id is not None:
            data["space_id"] = str(self.space_id)
        if self.run_id is not None:
            data["run_id"] = str(self.run_id)
            data["step"] = self.step
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
    ticket = event.type in TICKET_TYPES
    if event.type in SPACE_TYPES:
        if event.space_id is None:
            return None
        return LiveEvent(
            name=name,
            org_id=event.org_id,
            conversation_id=None,
            message_id=None,
            parent_id=None,
            user_id=None,
            space_id=event.space_id,
            sprint_id=_uuid(payload.get("sprint_id")),
            proposal_id=_uuid(payload.get("proposal_id")),
        )
    run = event.type == "run.progress"
    step = payload.get("step")
    return LiveEvent(
        name=name,
        org_id=event.org_id,
        conversation_id=_uuid(payload.get("conversation_id")),
        message_id=_uuid(payload.get("message_id")),
        parent_id=_uuid(payload.get("parent_id")),
        user_id=_uuid(payload.get("user_id")) if event.type in FOR_ONE_PERSON else None,
        ticket_id=_uuid(payload.get("ticket_id")) if ticket else None,
        space_id=event.space_id if ticket else None,
        run_id=_uuid(payload.get("run_id")) if run else None,
        step=step if run and isinstance(step, int) else None,
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
        keys = ("c", "m", "p", "u", "w", "s", "r", "n", "x")
        ids = {key: _strict_uuid(data.get(key)) for key in keys}
        org_id = _strict_uuid(data.get("o"))
        step = data.get("k")
        if step is not None and (not isinstance(step, int) or isinstance(step, bool)):
            raise TypeError("not a step")
    except (ValueError, TypeError, RecursionError):
        return None
    if org_id is None:
        return None
    return LiveEvent(
        data["t"],
        org_id,
        ids["c"],
        ids["m"],
        ids["p"],
        ids["u"],
        ids["w"],
        ids["s"],
        ids["r"],
        ids["n"],
        step,
        ids["x"],
    )


def _strict_uuid(value: object) -> uuid.UUID | None:
    """None for null; a UUID for its text; anything else is refused (ValueError)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("not an id")
    return uuid.UUID(value)
