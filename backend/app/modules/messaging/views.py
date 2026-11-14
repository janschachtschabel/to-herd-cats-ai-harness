"""Messages as their reader is shown them: with whom they mention, their reactions
summed up (`mine` from the reader's side), the author's name (a person's, or an
agent's through `agent_hooks`), and a system message's
timeline entry read from its body (a key with parameters, for the client to word),
the ids in it named (people, ticket statuses, parent tickets, sprints, linked pages). For
messages the reader has been allowed to see; at most seven queries for a whole page. A
linked page, a status, a sprint or a ticket the reader cannot see (or that is gone) is left out:
neither its name nor its id (review M4 P1; the raw body is never shown either, see
`MessageOut`)."""

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, space_ids_with
from app.core.actor import Actor
from app.core.principal import PrincipalType
from app.modules.messaging.agent_hooks import agent_hooks
from app.modules.messaging.models import Message, MessageKind
from app.modules.messaging.social_repository import (
    MentionRepository,
    ReactionRepository,
    ReactionSummary,
)
from app.modules.messaging.ticket_hooks import ticket_hooks
from app.modules.users.repository import UserRepository
from app.modules.wiki.visibility import PageReader

# Timeline keys whose `from`/`to` are ids, by what they name.
PERSON_KEYS = frozenset({"ticket.assigned", "ticket.unassigned"})
STATUS_KEYS = frozenset({"ticket.status_changed"})
TICKET_KEYS = frozenset({"ticket.parent_changed"})
SPRINT_KEYS = frozenset({"ticket.sprint_changed"})
PAGE_KEYS = frozenset({"ticket.page_linked", "ticket.page_unlinked"})


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
    tickets: dict[uuid.UUID, str]  # keys (`HC-12`)
    sprints: dict[uuid.UUID, str]
    pages: dict[uuid.UUID, str]  # these four: only those the reader sees

    def of(self, key: str, value: object) -> SystemValue | None:
        if not isinstance(value, str):
            return None
        ref = _uuid(value)
        if key in PERSON_KEYS:
            return SystemValue(value=value, name=self.people.get(ref) if ref else None)
        if key in PAGE_KEYS | STATUS_KEYS | TICKET_KEYS | SPRINT_KEYS:  # named only where seen
            name = self._seen(key, ref) if ref is not None else None
            return SystemValue(value=value, name=name) if name is not None else None
        return SystemValue(value=value, name=None)

    def _seen(self, key: str, ref: uuid.UUID) -> str | None:
        if key in PAGE_KEYS:
            return self.pages.get(ref)
        if key in STATUS_KEYS:
            return self.statuses.get(ref)
        if key in SPRINT_KEYS:
            return self.sprints.get(ref)
        return self.tickets.get(ref)


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
    agents = {
        m.author_id
        for m in messages
        if m.author_id is not None and m.author_type == PrincipalType.AGENT
    }
    agent_names = await agent_hooks().names(session, actor.org_id, agents) if agents else {}
    people |= {a for b in present if (a := _uuid(b.get("actor"))) is not None}
    people |= _refs(present, PERSON_KEYS)
    hooks = ticket_hooks()
    tickets = hooks.names(session, actor.org_id, space_ids_with(actor, Action.TICKET_READ))
    numbers = await tickets.numbers(_refs(present, TICKET_KEYS))
    names = _Names(
        people=await UserRepository(session).names(actor.org_id, people),
        statuses=await tickets.status_names(_refs(present, STATUS_KEYS)),
        tickets={ref: hooks.key(number) for ref, number in numbers.items()},
        sprints=await tickets.sprint_names(_refs(present, SPRINT_KEYS)),
        pages=await PageReader(session).titles(actor, _refs(present, PAGE_KEYS)),
    )
    return [
        MessageView(
            m,
            mentions.get(m.id, []),
            reactions.get(m.id, []),
            author_name=_author_name(m, names.people, agent_names),
            system=_system_entry(bodies[m.id], names),
        )
        for m in messages
    ]


def _author_name(
    message: Message, people: dict[uuid.UUID, str], agents: dict[uuid.UUID, str]
) -> str | None:
    if message.author_id is None:
        return None
    if message.author_type == PrincipalType.AGENT:
        return agents.get(message.author_id)
    return people.get(message.author_id)
