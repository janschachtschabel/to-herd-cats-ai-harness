"""What travels from the worker to every API process for live delivery (spec 6.4).

The outbox handler `publish_live` turns an event into a `NOTIFY herd_live` in the
handler's transaction (sent when it commits). The payload is compact JSON with ids
only, never content:

    {"t": <SSE event name>, "o": <org_id>, "c": <conversation_id|null>,
     "m": <message_id|null>, "p": <parent_id|null>, "u": <user_id|null>,
     "w": <ticket_id>, "s": <space_id> (ticket events only),
     "r": <sprint_id> (sprint events only, with "s"),
     "x": <proposal_id> (proposal events with "s"; `skill_proposal.changed` with "u"),
     "a": <author_id> (proposal events of a person's proposal only),
     "n": <run_id>, "k": <step> (`run.progress` only),
     "y": <automation_id> (`automation.changed`, with "u" and "s"),
     "b": <backup_run_id|null> (`backup.changed`, with "u"),
     "l": <calendar_id> (`calendar.changed`, with "s"),
     "e": <event_id> (`event.invited`, with "u")}

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
may edit pages there (who sees proposals), with the proposal's id, and for the
proposal's author when that is a person who may read the space (`a`, plan M6 task 6:
an author always hears of their proposal). `skill_proposal.changed` (plan M6 task 9)
is for one person `u` (who may decide the skill proposal `x`, or its author: the
handler writes one per person), with the proposal's id; so is `automation.changed`
(plan M7 task 7, for who may see the automation), with its id and its place's space
(`s`, null for a DM). `run.progress` (plan M5 task 6) names an agent's run as `n` and
its steps so far as `k`, for whoever may see its conversation `c`; a heartbeat's run
before it delivers anything names no `c` but its asker `u` (review M7, finding 5).
`backup.changed` (plan M9 task 13, `u` an owner, `b` the run) is sent directly, not
through the outbox (`modules/backups/live.py`). `calendar.changed` (plan M10, from
`modules/calendars/live.py`) is for the space `s`, for its members alone (never by
admin power), with the space's and the calendar's id `l`; `event.invited` (plan M10
task 4: invited, the time changed, called off) is for the one person `u` invited to
the event `e`, who may not be a member of its space. Every
API process's hub (`live.py`) decodes it again (`live_decode.py`); anything it cannot use
is dropped.
Payloads stay far below Postgres' 8000-byte limit (about 330 bytes).

This module is the shape (`LiveEvent`, names, the frame); the worker's side, from an
outbox event to the NOTIFY, is `live_publish.py`; the API processes' side, from the
payload back to a `LiveEvent`, is `live_decode.py`.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any

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
    # A run's card was decided or answered (plan M6 task 7): its conversation reloads it.
    "approval.decided": "card.changed",
    "approval.settled": "card.changed",  # what became of a released call: ran or stale
    "question.answered": "card.changed",
    "skill_proposal.changed": "skill_proposal.changed",
    "automation.changed": "automation.changed",
    "calendar_event.invited": "event.invited",
}
BACKUP = "backup.changed"  # sent directly (`modules/backups/live.py`), not from the outbox
CALENDAR = "calendar.changed"  # published by `modules/calendars/live.py`
INVITED = "event.invited"
LIVE_NAMES = frozenset(LIVE_TYPES.values()) | {BACKUP, CALENDAR}
TICKET_TYPES = frozenset({"ticket.created", "ticket.updated"})
# Events for a space (no conversation, no person): sprints for whoever may read tickets
# there, proposals for whoever may edit pages there (`LiveEvent.space_action`).
SPRINT_TYPES = frozenset({"sprint.created", "sprint.updated", "sprint.started", "sprint.closed"})
PROPOSAL_TYPES = frozenset(t for t, name in LIVE_TYPES.items() if name == "proposal.changed")
SPACE_TYPES = SPRINT_TYPES | PROPOSAL_TYPES
SKILL_PROPOSAL = "skill_proposal.changed"
AUTOMATION = "automation.changed"
# Events for one person: the payload's `user_id` is who gets them.
FOR_ONE_PERSON = frozenset(
    {
        "notification.created",
        "conversation.read",
        "activity.changed",
        "access.changed",
        "skill_proposal.changed",
        "automation.changed",
        "run.progress",  # a heartbeat's before it delivers: its asker alone, no `c`
        "calendar_event.invited",
    }
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
    author_id: uuid.UUID | None = None  # a person's proposal: its author gets it too
    automation_id: uuid.UUID | None = None  # automation.changed only (with `space_id`)
    backup_id: uuid.UUID | None = None  # backup.changed only
    calendar_id: uuid.UUID | None = None  # calendar.changed only (with `space_id`)
    event_id: uuid.UUID | None = None  # event.invited only (with `user_id`)

    @property
    def for_space(self) -> bool:
        """For people of the space (`space_action`): neither a conversation nor a
        person."""
        return self.conversation_id is None and self.user_id is None and self.space_id is not None

    @property
    def space_action(self) -> Action:
        """What a space event's recipients may do in the space."""
        if self.name == CALENDAR:
            return Action.CALENDAR_READ
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
        if self.author_id is not None:
            data["a"] = str(self.author_id)
        if self.automation_id is not None:
            data["y"] = str(self.automation_id)
        if self.backup_id is not None:
            data["b"] = str(self.backup_id)
        if self.calendar_id is not None:
            data["l"] = str(self.calendar_id)
        if self.event_id is not None:
            data["e"] = str(self.event_id)
        return json.dumps(data, separators=(",", ":"))

    def frame(self) -> bytes:
        """The server-sent event: its name and the ids a client reloads by (a ticket
        event also `ticket_id` and `space_id`; a sprint event only `space_id` and
        `sprint_id`; a proposal event only `space_id` and `proposal_id`)."""
        if self.for_space and self.name == CALENDAR:
            return sse_frame(
                self.name, {"space_id": str(self.space_id), "calendar_id": _text(self.calendar_id)}
            )
        if self.for_space and self.name == "proposal.changed":
            return sse_frame(
                self.name, {"space_id": str(self.space_id), "proposal_id": _text(self.proposal_id)}
            )
        if self.for_space:
            return sse_frame(
                self.name, {"space_id": str(self.space_id), "sprint_id": _text(self.sprint_id)}
            )
        if self.name == BACKUP:
            return sse_frame(self.name, {"backup_id": _text(self.backup_id)})
        if self.name == INVITED:
            return sse_frame(self.name, {"event_id": _text(self.event_id)})
        if self.name == AUTOMATION:
            return sse_frame(
                self.name,
                {"automation_id": _text(self.automation_id), "space_id": _text(self.space_id)},
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
        if self.proposal_id is not None:  # skill_proposal.changed
            data["proposal_id"] = str(self.proposal_id)
        return sse_frame(self.name, data)


def sse_frame(name: str, data: dict[str, Any]) -> bytes:
    return f"event: {name}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n".encode()


def _text(value: uuid.UUID | None) -> str | None:
    return None if value is None else str(value)
