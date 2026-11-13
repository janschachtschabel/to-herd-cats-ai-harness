"""Messages as their reader is shown them: with whom they mention, their reactions
summed up (`mine` from the reader's side), the author's name, and a system message's
timeline entry read from its body (a key with parameters, for the client to word),
the ids in it named (people, ticket statuses, parent tickets). For messages the
reader has been allowed to see; at most five queries for a whole page."""

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.modules.messaging.models import Message, MessageKind
from app.modules.messaging.social_repository import (
    MentionRepository,
    ReactionRepository,
    ReactionSummary,
)
from app.modules.tickets.models import ticket_key
from app.modules.tickets.name_repository import TicketNameRepository
from app.modules.users.repository import UserRepository

# Timeline keys whose `from`/`to` are ids, by what they name.
PERSON_KEYS = frozenset({"ticket.assigned", "ticket.unassigned"})
STATUS_KEYS = frozenset({"ticket.status_changed"})
TICKET_KEYS = frozenset({"ticket.parent_changed"})


@dataclass(frozen=True, slots=True)
class SystemValue:
    """A value a timeline entry changed from or to, and its name where it is an id of
    something named (null if that is gone, or for plain values: dates, priorities)."""

    value: str
    name: str | None


@dataclass(frozen=True, slots=True)
class SystemEntry:
    """A timeline entry: the page or ticket event (`key`), who caused it, the restored
    version's `number` (only for `page.version_restored`), and for a ticket change the
    `old` and `new` value (null where there was none, and for title and
    description, which the timeline never carries)."""

    key: str
    actor_id: uuid.UUID | None
    actor_name: str | None
    number: int | None
    old: SystemValue | None = None
    new: SystemValue | None = None


@dataclass(frozen=True, slots=True)
class _Names:
    people: dict[uuid.UUID, str]
    statuses: dict[uuid.UUID, str]
    tickets: dict[uuid.UUID, int]

    def of(self, key: str, value: object) -> SystemValue | None:
        if not isinstance(value, str):
            return None
        ref = _uuid(value)
        name: str | None = None
        if ref is not None and key in PERSON_KEYS:
            name = self.people.get(ref)
        elif ref is not None and key in STATUS_KEYS:
            name = self.statuses.get(ref)
        elif ref is not None and key in TICKET_KEYS:
            number = self.tickets.get(ref)
            name = ticket_key(number) if number is not None else None
        return SystemValue(value=value, name=name)


@dataclass(frozen=True, slots=True)
class MessageView:
    message: Message
    mentions: list[uuid.UUID]
    reactions: list[ReactionSummary]
    author_name: str | None = None
    system: SystemEntry | None = None


def _system_body(message: Message) -> dict[str, object] | None:
    """The parameters a system message was written with (`threads.page_timeline`)."""
    if message.kind != MessageKind.SYSTEM:
        return None
    try:
        body = json.loads(message.body_md)
    except ValueError:
        return None
    return body if isinstance(body, dict) and isinstance(body.get("key"), str) else None


def _uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value is not None else None
    except ValueError:
        return None


def _refs(bodies: Sequence[dict[str, object]], keys: frozenset[str]) -> set[uuid.UUID]:
    """The ids that bodies with one of `keys` changed from or to."""
    found: set[uuid.UUID] = set()
    for body in bodies:
        if body["key"] in keys:
            found |= {r for v in (body.get("from"), body.get("to")) if (r := _uuid(v))}
    return found


def _system_entry(body: dict[str, object] | None, names: _Names) -> SystemEntry | None:
    if body is None:
        return None
    key = str(body["key"])
    actor = _uuid(body.get("actor"))
    number = body.get("number")
    return SystemEntry(
        key=key,
        actor_id=actor if actor in names.people else None,
        actor_name=names.people.get(actor) if actor else None,
        number=number if isinstance(number, int) else None,
        old=names.of(key, body.get("from")),
        new=names.of(key, body.get("to")),
    )


async def message_views(
    session: AsyncSession, actor: Actor, messages: Sequence[Message]
) -> list[MessageView]:
    ids = [m.id for m in messages]
    mentions = await MentionRepository(session, actor.org_id).of(ids)
    reactions = await ReactionRepository(session, actor.org_id).summaries(ids, actor.principal.id)
    bodies = {m.id: _system_body(m) for m in messages}
    present = [b for b in bodies.values() if b is not None]
    people = {m.author_id for m in messages if m.author_id is not None}
    people |= {a for b in present if (a := _uuid(b.get("actor"))) is not None}
    people |= _refs(present, PERSON_KEYS)
    tickets = TicketNameRepository(session, actor.org_id)
    names = _Names(
        people=await UserRepository(session).names(actor.org_id, people),
        statuses=await tickets.status_names(_refs(present, STATUS_KEYS)),
        tickets=await tickets.numbers(_refs(present, TICKET_KEYS)),
    )
    return [
        MessageView(
            m,
            mentions.get(m.id, []),
            reactions.get(m.id, []),
            author_name=names.people.get(m.author_id) if m.author_id else None,
            system=_system_entry(bodies[m.id], names),
        )
        for m in messages
    ]
