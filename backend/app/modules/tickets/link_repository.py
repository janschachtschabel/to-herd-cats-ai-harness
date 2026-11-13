"""The SQL of links between tickets and pages (plan M4 decision 11). Scoped like
`TicketRepository` (the actor's organisation, the spaces where it may read tickets);
the page side is filtered by the wiki's own rule (`PageReader.seen`), passed in as
SQL. Each list keeps only rows whose both ends the actor sees, in the statement."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert

from app.modules.spaces.models import Space
from app.modules.tickets.models import TicketPageLink, WorkItem
from app.modules.tickets.repository import TicketRepository, TicketView
from app.modules.wiki.models import Page


@dataclass(frozen=True, slots=True)
class LinkedPage:
    page_id: uuid.UUID
    space_id: uuid.UUID
    space_name: str
    title: str
    path: str
    linked_at: datetime


class LinkRepository(TicketRepository):
    async def count(self, ticket_id: uuid.UUID) -> int:
        """Every link of the ticket, seen or not (the limit counts them all)."""
        stmt = select(func.count()).where(TicketPageLink.work_item_id == ticket_id)
        return int(await self.session.scalar(stmt) or 0)

    async def link(self, ticket_id: uuid.UUID, page_id: uuid.UUID) -> bool:
        """Whether the link is new."""
        stmt = (
            insert(TicketPageLink)
            .values(org_id=self.scope.org_id, work_item_id=ticket_id, page_id=page_id)
            .on_conflict_do_nothing()
            .returning(TicketPageLink.page_id)
        )
        return (await self.session.scalar(stmt)) is not None

    async def unlink(self, ticket_id: uuid.UUID, page_id: uuid.UUID) -> bool:
        """Whether there was such a link."""
        stmt = (
            delete(TicketPageLink)
            .where(
                TicketPageLink.org_id == self.scope.org_id,
                TicketPageLink.work_item_id == ticket_id,
                TicketPageLink.page_id == page_id,
            )
            .returning(TicketPageLink.page_id)
        )
        return (await self.session.scalar(stmt)) is not None

    async def pages(
        self,
        ticket_id: uuid.UUID,
        seen: ColumnElement[bool],
        before: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[LinkedPage]:
        """The pages of a ticket the actor sees that it sees too (`seen`), last
        linked first."""
        stmt = (
            select(
                Page.id,
                Page.space_id,
                Space.name,
                Page.title,
                Page.path,
                TicketPageLink.linked_at,
            )
            .join(Page, Page.id == TicketPageLink.page_id)
            .join(Space, Space.id == Page.space_id)
            .where(TicketPageLink.org_id == self.scope.org_id)
            .where(TicketPageLink.work_item_id == ticket_id, seen)
            .order_by(TicketPageLink.linked_at.desc(), Page.id.desc())
            .limit(limit)
        )
        if before is not None:
            stmt = stmt.where(
                tuple_(TicketPageLink.linked_at, TicketPageLink.page_id) < tuple_(*before)
            )
        return [LinkedPage(*row) for row in await self.session.execute(stmt)]

    async def tickets(
        self, page_id: uuid.UUID, before_number: int | None, limit: int
    ) -> list[TicketView]:
        """The tickets the actor sees among those linking a page it sees, newest
        first."""
        linking = select(TicketPageLink.work_item_id).where(
            TicketPageLink.org_id == self.scope.org_id, TicketPageLink.page_id == page_id
        )
        stmt = self._views().where(WorkItem.id.in_(linking))
        if before_number is not None:
            stmt = stmt.where(WorkItem.number < before_number)
        rows = await self.session.execute(stmt.order_by(WorkItem.number.desc()).limit(limit))
        return [self._view(row) for row in rows]
