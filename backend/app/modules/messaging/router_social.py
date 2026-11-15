"""Routes of reactions, read positions and unread counters. `unread` must be included
before the conversation routes (`/conversations/{conversation_id}` would take it)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.messaging.message_schemas import (
    ReactionOut,
    ReadPosition,
    ReadPositionOut,
    UnreadOut,
)
from app.modules.messaging.reactions import ReactionService
from app.modules.messaging.reads import ReadService

unread = APIRouter(prefix="/conversations", tags=["messaging"])
reads = APIRouter(prefix="/conversations", tags=["messaging"])
reactions = APIRouter(prefix="/messages", tags=["messaging"])

Emoji = Annotated[str, Path(description="exactly one emoji (URL-encoded)")]


@unread.get("/unread", response_model=Page[UnreadOut])
async def list_unread(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[UnreadOut]:
    """Every conversation the caller sees with something unread, by id."""
    page = await ReadService(session).unread(actor, params)
    items = [
        UnreadOut(conversation_id=u.conversation_id, unread=u.unread, mentions=u.mentions)
        for u in page.items
    ]
    return Page[UnreadOut](items=items, next_cursor=page.next_cursor)


@reads.get("/{conversation_id}/read", response_model=ReadPositionOut)
async def read_position(
    conversation_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> ReadPositionOut:
    """The caller's read position in the conversation (nulls before she read any)."""
    found = await ReadService(session).position(actor, conversation_id)
    message_id, at = found if found is not None else (None, None)
    return ReadPositionOut(last_read_message_id=message_id, last_read_message_at=at)


@reads.post("/{conversation_id}/read", status_code=204)
async def mark_read(
    conversation_id: uuid.UUID, body: ReadPosition, actor: ActorDep, session: SessionDep
) -> None:
    """Read up to a message of the conversation (never backwards)."""
    await ReadService(session).mark(actor, conversation_id, body.message_id)


@reactions.put("/{message_id}/reactions/{emoji}", response_model=list[ReactionOut])
async def react(
    message_id: uuid.UUID, emoji: Emoji, actor: ActorDep, session: SessionDep
) -> list[ReactionOut]:
    """Add the caller's reaction (again: no change); the message's reactions."""
    summary = await ReactionService(session).react(actor, message_id, emoji)
    return [ReactionOut.of(r) for r in summary]


@reactions.delete("/{message_id}/reactions/{emoji}", response_model=list[ReactionOut])
async def unreact(
    message_id: uuid.UUID, emoji: Emoji, actor: ActorDep, session: SessionDep
) -> list[ReactionOut]:
    """Take the caller's reaction back (none: no change); the message's reactions."""
    summary = await ReactionService(session).unreact(actor, message_id, emoji)
    return [ReactionOut.of(r) for r in summary]
