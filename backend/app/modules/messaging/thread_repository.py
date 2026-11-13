"""The SQL of page and ticket threads, for the services (after the caller's check of the
page or ticket) and the timeline handlers (no actor: the event's organisation).

- One thread per page (`conversation.page_id` is unique) and per ticket
  (`conversation.work_item_id`): the first to ask inserts it, everyone else (also
  concurrently) reads the one that won.
- A system message refers to its event by `client_id`, unique among system messages,
  so a second delivery of an event inserts nothing. (A ticket event may have several
  entries: each has an id derived from the event's and its own name.)
- A system message takes the event's time, as `created_at` and in its id (a UUIDv7 of
  that moment, to the microsecond): messages are listed by id, so the timeline follows
  the changes, not the order the worker happened to handle them in (retries, several
  workers). The entries of one event are `offset` microseconds apart, in their order.
"""

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.models import (
    SYSTEM_AUTHOR,
    Conversation,
    ConversationKind,
    Message,
    MessageKind,
)
from app.modules.tickets.models import WorkItem
from app.modules.wiki.models import Page


class ThreadRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def add_system(
        self,
        thread: Conversation,
        client_id: uuid.UUID,
        body_md: str,
        at: datetime,
        offset: int = 0,
    ) -> Message | None:
        """The system message `client_id` (an event's, or one entry of it); None if it
        exists already."""
        stmt = (
            insert(Message)
            .values(
                id=_id_at(at + timedelta(microseconds=offset)),
                org_id=self.org_id,
                conversation_id=thread.id,
                author_type=SYSTEM_AUTHOR,
                author_id=None,
                kind=MessageKind.SYSTEM,
                body_md=body_md,
                client_id=client_id,
                created_at=at,
            )
            .on_conflict_do_nothing(
                index_elements=["client_id"], index_where=text("author_type = 'system'")
            )
            .returning(Message)
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def system_message(self, client_id: uuid.UUID) -> Message | None:
        stmt = select(Message).where(
            Message.org_id == self.org_id,
            Message.author_type == SYSTEM_AUTHOR,
            Message.client_id == client_id,
        )
        return await self.session.scalar(stmt)

    async def _thread(self, values: dict[str, object], key: str) -> Conversation:
        """The thread with `values`, inserted unless one with the same `key` exists
        (looked up first: it exists nearly always, review M4 P3)."""
        column = getattr(Conversation, key)
        found = select(Conversation).where(
            Conversation.org_id == self.org_id, column == values[key]
        )
        existing = await self.session.scalar(found)
        if existing is not None:
            return existing
        stmt = (
            insert(Conversation)
            .values(org_id=self.org_id, **values)
            .on_conflict_do_nothing(index_elements=[key])
            .returning(Conversation)
            .execution_options(populate_existing=True)
        )
        created = (await self.session.scalars(stmt)).one_or_none()
        if created is not None:
            return created
        existing = await self.session.scalar(found)
        assert existing is not None  # the row that won the conflict
        return existing


class PageThreadRepository(ThreadRepository):
    async def page(self, page_id: uuid.UUID) -> Page | None:
        """The page in the organisation, in the trash or not."""
        stmt = select(Page).where(Page.org_id == self.org_id, Page.id == page_id)
        return await self.session.scalar(stmt)

    async def thread_for(self, page: Page) -> Conversation:
        """The page's thread, inserted if it has none yet."""
        values = {
            "kind": ConversationKind.THREAD_PAGE,
            "space_id": page.space_id,
            "page_id": page.id,
        }
        return await self._thread(values, "page_id")


class TicketThreadRepository(ThreadRepository):
    async def ticket_and_thread(self, ticket_id: uuid.UUID) -> tuple[WorkItem, Conversation] | None:
        """The ticket and its thread (inserted if it has none yet), in one statement
        when it has one; None if the ticket is gone."""
        stmt = (
            select(WorkItem, Conversation)
            .outerjoin(
                Conversation,
                and_(Conversation.org_id == self.org_id, Conversation.work_item_id == WorkItem.id),
            )
            .where(WorkItem.org_id == self.org_id, WorkItem.id == ticket_id)
        )
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        ticket, thread = row
        return ticket, thread if thread is not None else await self.thread_for(ticket)

    async def thread_for(self, ticket: WorkItem) -> Conversation:
        """The ticket's thread, inserted if it has none yet."""
        values = {
            "kind": ConversationKind.THREAD_TICKET,
            "space_id": ticket.space_id,
            "work_item_id": ticket.id,
        }
        return await self._thread(values, "work_item_id")

    async def thread_ids(self, ticket_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
        """The threads of these tickets (ticket id → conversation id)."""
        if not ticket_ids:
            return {}
        stmt = select(Conversation.work_item_id, Conversation.id).where(
            Conversation.org_id == self.org_id, Conversation.work_item_id.in_(ticket_ids)
        )
        return {row[0]: row[1] for row in await self.session.execute(stmt) if row[0]}


def _id_at(at: datetime) -> uuid.UUID:
    """A new UUIDv7 whose time is `at`: the milliseconds in `unix_ts_ms`, the rest of
    the microsecond in `rand_a` (RFC 9562, 6.2 method 3), so ids sort by microsecond."""
    micros = int(at.timestamp()) * 1_000_000 + at.microsecond
    millis, fraction = divmod(micros, 1_000)
    rand_a = fraction * 4096 // 1_000
    value = (millis << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | secrets.randbits(62)
    return uuid.UUID(int=value)
