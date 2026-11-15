"""Links between tickets and wiki pages (spec 10, plan M4 decision 11).

A ticket links pages of any space. Linking and unlinking need `ticket.edit` on the
ticket and sight of the page (404 `page.not_found` otherwise, as for an unknown id);
both are idempotent, and each real change is one `ticket.updated` event naming
`page` (timeline: `ticket.page_linked` / `ticket.page_unlinked`). A link is no field
of the ticket: it takes no version and leaves the ticket's alone.

Each side lists only links whose both ends the caller sees, filtered in SQL: a ticket's
pages, and a page's tickets. A page in the trash keeps its links but shows none (it
is not seen); purging it removes them (foreign key). A ticket links at most
`MAX_LINKS` pages; the ticket row is locked while one is added, so the limit holds
under concurrent requests.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Actor
from app.core.authorship import Authorship
from app.core.errors import ValidationFailed
from app.core.pagination import PageParams, decode_cursor, encode_cursor
from app.modules.tickets import listing
from app.modules.tickets.base import (
    editable,
    emit_change,
    readable,
    ticket_repository,
    with_tags,
)
from app.modules.tickets.events import TICKET_UPDATED, Field
from app.modules.tickets.link_repository import LinkedPage, LinkRepository
from app.modules.tickets.models import WorkItem
from app.modules.tickets.repository import TicketView
from app.modules.wiki.visibility import PageReader

MAX_LINKS = 50  # pages per ticket


class TicketLinks:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _repo(self, actor: Actor) -> LinkRepository:
        return LinkRepository(self.session, ticket_repository(self.session, actor).scope)

    async def link(
        self, actor: Actor, number: int, page_id: uuid.UUID, by: Authorship | None = None
    ) -> bool:
        """Whether the link is new; `by`: written for an agent (its run)."""
        _, ticket = await editable(self.session, actor, number)
        await PageReader(self.session).readable(actor, page_id)
        links = self._repo(actor)
        if not await links.link(ticket.id, page_id):
            return False  # already linked: nothing changes
        if await links.count(ticket.id) > MAX_LINKS:  # the error undoes the insert
            raise ValidationFailed(
                f"A ticket links at most {MAX_LINKS} pages", code="ticket.too_many_pages"
            )
        await self._emit(actor, ticket, None, page_id, by)
        return True

    async def unlink(self, actor: Actor, number: int, page_id: uuid.UUID) -> None:
        _, ticket = await editable(self.session, actor, number)
        await PageReader(self.session).readable(actor, page_id)
        if await self._repo(actor).unlink(ticket.id, page_id):
            await self._emit(actor, ticket, page_id, None)

    async def pages_of(
        self, actor: Actor, number: int, params: PageParams
    ) -> pagination.Page[LinkedPage]:
        """The ticket's pages the caller sees, last linked first."""
        ticket = await readable(self.session, actor, ticket_repository(self.session, actor), number)
        before = decode_cursor(params.cursor) if params.cursor else None
        seen = PageReader(self.session).seen(actor)
        rows = await self._repo(actor).pages(ticket.id, seen, before, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = encode_cursor(items[-1].linked_at, items[-1].page_id) if more else None
        return pagination.Page[LinkedPage](items=items, next_cursor=cursor)

    async def tickets_of(
        self, actor: Actor, page_id: uuid.UUID, params: PageParams
    ) -> pagination.Page[TicketView]:
        """The tickets linking a page the caller sees that it may see, newest first."""
        page = await PageReader(self.session).readable(actor, page_id)
        after = listing.decode(listing.Sort.NUMBER, params.cursor) if params.cursor else None
        rows = await self._repo(actor).tickets(
            page.id, after.number if after else None, params.limit + 1
        )
        items = await with_tags(self.session, actor, rows[: params.limit])
        cursor = None
        if len(rows) > params.limit:
            last = listing.Position(0, items[-1].ticket.number)
            cursor = listing.encode(listing.Sort.NUMBER, last)
        return pagination.Page[TicketView](items=items, next_cursor=cursor)

    async def _emit(
        self,
        actor: Actor,
        ticket: WorkItem,
        old: uuid.UUID | None,
        new: uuid.UUID | None,
        by: Authorship | None = None,
    ) -> None:
        changes = {Field.PAGE: (old, new)}
        await emit_change(self.session, actor, TICKET_UPDATED, ticket, changes, by)
