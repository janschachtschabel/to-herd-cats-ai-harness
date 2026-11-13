"""Messages as their reader is shown them: with whom they mention, their reactions
summed up (`mine` from the reader's side), the author's name, and a system message's
timeline entry read from its body (a key with parameters, for the client to word).
For messages the reader has been allowed to see; three queries for a whole page."""

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
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, slots=True)
class SystemEntry:
    """A page-thread timeline entry: the page event (`key`), who caused it, and the
    restored version's `number` (only for `page.version_restored`)."""

    key: str
    actor_id: uuid.UUID | None
    actor_name: str | None
    number: int | None


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


def _system_entry(
    body: dict[str, object] | None, names: dict[uuid.UUID, str]
) -> SystemEntry | None:
    if body is None:
        return None
    actor = _uuid(body.get("actor"))
    number = body.get("number")
    return SystemEntry(
        key=str(body["key"]),
        actor_id=actor if actor in names else None,
        actor_name=names.get(actor) if actor else None,
        number=number if isinstance(number, int) else None,
    )


async def message_views(
    session: AsyncSession, actor: Actor, messages: Sequence[Message]
) -> list[MessageView]:
    ids = [m.id for m in messages]
    mentions = await MentionRepository(session, actor.org_id).of(ids)
    reactions = await ReactionRepository(session, actor.org_id).summaries(ids, actor.principal.id)
    bodies = {m.id: _system_body(m) for m in messages}
    people = {m.author_id for m in messages if m.author_id is not None}
    people |= {a for b in bodies.values() if b and (a := _uuid(b.get("actor"))) is not None}
    names = await UserRepository(session).names(actor.org_id, people)
    return [
        MessageView(
            m,
            mentions.get(m.id, []),
            reactions.get(m.id, []),
            author_name=names.get(m.author_id) if m.author_id else None,
            system=_system_entry(bodies[m.id], names),
        )
        for m in messages
    ]
