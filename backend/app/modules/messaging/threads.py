"""Threads: one level of replies under a top-level message (spec 6.1), and the
threads of wiki pages with their system timeline (`ThreadService`, `page_timeline`).

A reply names a top-level message of the same conversation that the actor can see;
anything else is 422 `message.bad_parent` (an unseen or unknown parent reads the
same). The parent is locked while the reply is written, so concurrent replies count
one after the other and `reply_count` and `last_reply_at` stay right.
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.errors import ValidationFailed
from app.core.outbox import Event, emit
from app.modules.messaging.message_repository import MessageRepository
from app.modules.messaging.models import Conversation, Message
from app.modules.messaging.thread_repository import PageThreadRepository
from app.modules.wiki.events import PAGE_EVENTS
from app.modules.wiki.visibility import PageReader


def bad_parent() -> ValidationFailed:
    return ValidationFailed("A reply goes under a top-level message", code="message.bad_parent")


async def lock_parent(
    repo: MessageRepository, conversation: Conversation, parent_id: uuid.UUID
) -> Message:
    """The parent of a new reply, locked until the transaction ends."""
    parent = await repo.get(parent_id, lock=True)
    if parent is None or parent.conversation_id != conversation.id or parent.parent_id:
        raise bad_parent()
    return parent


def count_reply(parent: Message, reply: Message) -> None:
    """The parent (locked) has one more reply."""
    parent.reply_count += 1
    last = parent.last_reply_at
    parent.last_reply_at = reply.created_at if last is None else max(last, reply.created_at)


class ThreadService:
    """Page threads (spec 6.1): exactly one conversation per page, seen by whoever
    sees the page (drafts with `page.edit`, nothing while it is in the trash; the rule
    lives in `repository.visible_conversations`), written in with `channel.post` in
    the page's space."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_page(self, actor: Actor, page_id: uuid.UUID) -> Conversation:
        """The page's thread, created on first access; 404 `page.not_found` when the
        actor may not see the page."""
        page = await PageReader(self.session).readable(actor, page_id)
        return await PageThreadRepository(self.session, actor.org_id).thread_for(page)


async def page_timeline(session: AsyncSession, event: Event) -> None:
    """Outbox handler of the wiki's page events (`wiki/events.py`): one system message
    in the page's thread per event, its body a key with parameters for the client to
    word (`{"key": "page.published", "actor": "<id>"}`), never text. Idempotent: the
    message refers to the event (`client_id`). A page purged meanwhile gets nothing.
    The new message is emitted (`message.created`) for live delivery; it notifies
    nobody (`notify_on_message` skips system messages)."""
    if event.subject_type != "page" or event.type not in PAGE_EVENTS:
        return
    repo = PageThreadRepository(session, event.org_id)
    page = await repo.page(event.subject_id)
    if page is None:
        return
    thread = await repo.thread_for(page)
    body: dict[str, object] = {"key": event.type, "actor": str(event.actor.id)}
    number = event.payload.get("number")
    if isinstance(number, int):
        body["number"] = number
    message = await repo.add_system(thread, event.id, json.dumps(body), event.created_at)
    if message is None:
        return
    await emit(
        session,
        type="message.created",
        actor=event.acting,
        space_id=page.space_id,
        subject_type="message",
        subject_id=message.id,
        payload={
            "conversation_id": str(thread.id),
            "message_id": str(message.id),
            "parent_id": None,
        },
    )
