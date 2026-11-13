"""Threads: one level of replies under a top-level message (spec 6.1).

A reply names a top-level message of the same conversation that the actor can see;
anything else is 422 `message.bad_parent` (an unseen or unknown parent reads the
same). The parent is locked while the reply is written, so concurrent replies count
one after the other and `reply_count` and `last_reply_at` stay right.
"""

import uuid

from app.core.errors import ValidationFailed
from app.modules.messaging.message_repository import MessageRepository
from app.modules.messaging.models import Conversation, Message


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
