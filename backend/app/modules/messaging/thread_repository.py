"""The SQL of page threads, for the thread service (after the caller's page check) and
the timeline handler (no actor: the event's organisation).

- One thread per page (`conversation.page_id` is unique): the first to ask inserts it,
  everyone else (also concurrently) reads the one that won.
- A system message refers to its event by `client_id`, unique among system messages,
  so a second delivery of an event inserts nothing.
"""

import uuid
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.models import (
    SYSTEM_AUTHOR,
    Conversation,
    ConversationKind,
    Message,
    MessageKind,
)
from app.modules.wiki.models import Page


class PageThreadRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def page(self, page_id: uuid.UUID) -> Page | None:
        """The page in the organisation, in the trash or not."""
        stmt = select(Page).where(Page.org_id == self.org_id, Page.id == page_id)
        return await self.session.scalar(stmt)

    async def thread_for(self, page: Page) -> Conversation:
        """The page's thread, inserted if it has none yet."""
        stmt = (
            insert(Conversation)
            .values(
                org_id=self.org_id,
                kind=ConversationKind.THREAD_PAGE,
                space_id=page.space_id,
                page_id=page.id,
            )
            .on_conflict_do_nothing(index_elements=["page_id"])
            .returning(Conversation)
            .execution_options(populate_existing=True)
        )
        created = (await self.session.scalars(stmt)).one_or_none()
        if created is not None:
            return created
        existing = await self.session.scalar(
            select(Conversation).where(
                Conversation.org_id == self.org_id, Conversation.page_id == page.id
            )
        )
        assert existing is not None  # the row that won the conflict
        return existing

    async def add_system(
        self, thread: Conversation, event_id: uuid.UUID, body_md: str, at: datetime
    ) -> Message | None:
        """The system message of event `event_id`; None if it exists already."""
        stmt = (
            insert(Message)
            .values(
                org_id=self.org_id,
                conversation_id=thread.id,
                author_type=SYSTEM_AUTHOR,
                author_id=None,
                kind=MessageKind.SYSTEM,
                body_md=body_md,
                client_id=event_id,
                created_at=at,
            )
            .on_conflict_do_nothing(
                index_elements=["client_id"], index_where=text("author_type = 'system'")
            )
            .returning(Message)
        )
        return (await self.session.scalars(stmt)).one_or_none()
