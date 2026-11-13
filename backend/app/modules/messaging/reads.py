"""Read positions and unread counters (spec 6.1, review focus 5).

A person marks a conversation read up to one of its messages; the position only
moves forward (an older message changes nothing), and only a move is emitted
(`conversation.read`, with the reader's id: it is delivered to that person only).
The counters list every conversation the person may see at the time of asking with
something unread, in one query filtered by visibility in SQL: a conversation gone
from view (a membership removed) is gone from the counters at once. System messages
(a page's timeline) are never unread, and a page thread counts only once the person
has a read position in it (has opened it): every page has a thread.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.outbox import emit
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.messaging.service import MessageService, message_not_found
from app.modules.messaging.social_repository import ReadRepository, Unread


class ReadService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.messages = MessageService(session)

    async def mark(self, actor: Actor, conversation_id: uuid.UUID, message_id: uuid.UUID) -> None:
        """Read up to `message_id`, a message of the conversation (else 404)."""
        reader = self.messages.reader
        conversation = await reader.readable(actor, conversation_id)
        message = await self.messages.repo(actor).get(message_id)
        if message is None or message.conversation_id != conversation.id:
            raise message_not_found()
        if not await ReadRepository(self.session, reader.scope(actor)).advance(
            conversation.id, message.id
        ):
            return
        await emit(
            self.session,
            type="conversation.read",
            actor=actor,
            space_id=conversation.space_id,
            subject_type="conversation",
            subject_id=conversation.id,
            payload={
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "user_id": str(actor.principal.id),
            },
        )

    async def unread(self, actor: Actor, params: PageParams) -> Page[Unread]:
        """The actor's visible conversations with unread messages or mentions, by id."""
        after = decode_id_cursor(params.cursor) if params.cursor else None
        repo = ReadRepository(self.session, self.messages.reader.scope(actor))
        rows = await repo.unread_page(after, params.limit + 1)
        return id_page(rows, params.limit, lambda u: u.conversation_id)
