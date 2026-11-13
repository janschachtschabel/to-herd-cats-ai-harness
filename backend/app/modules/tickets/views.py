"""Ticket views (spec 10, plan M4 task 5): the board of a space, the epic overview and
the counts for the sidebar. "My tickets" is the list (`assignee=me`, categories open,
active and review).

Each view of a space needs `ticket.read` there (404 `space.not_found` otherwise, as
for an unknown id); a status of another space is 404 `ticket_status.not_found`. Every
number and every ticket comes from SQL filtered by the spaces the actor may read
tickets in; each call is a fixed number of statements (`view_repository.py`).

- Board: the space's statuses in order, each with how many tickets it holds under
  the filters and the first `limit` of them in board order (decision 8); a column's
  `next_cursor` continues it (`column`).
- Epics: the space's epics, newest first, each with its children per category.
- Counts: the caller's tickets that are open, active or in review.
"""

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require
from app.core.errors import ValidationFailed
from app.core.pagination import PageParams
from app.modules.tickets import listing
from app.modules.tickets.base import ticket_repository, with_tags
from app.modules.tickets.listing import Filters
from app.modules.tickets.models import StatusCategory, TicketStatus
from app.modules.tickets.repository import TicketView
from app.modules.tickets.statuses import status_not_found, status_repository
from app.modules.tickets.view_repository import BoardPosition, ViewRepository, board_position


@dataclass(frozen=True, slots=True)
class Column:
    status: TicketStatus
    count: int
    items: list[TicketView]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class Epic:
    view: TicketView
    children: dict[StatusCategory, int]


def encode(position: BoardPosition) -> str:
    raw = json.dumps([position.rank, position.due.isoformat(), position.number]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode(cursor: str) -> BoardPosition:
    """Anything that is not a board cursor is 422 (never a 500)."""
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        rank, due, number = json.loads(raw.decode())
        ints = type(rank) is int and type(number) is int
        if not ints or not -10 < rank <= 0 or not 0 <= number < 2**31:
            raise ValueError("not a board cursor")
        return BoardPosition(rank, date.fromisoformat(due), number)
    except Exception as exc:
        raise ValidationFailed("Invalid cursor", code="validation_failed") from exc


class TicketViews:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _repo(self, actor: Actor) -> ViewRepository:
        return ViewRepository(self.session, ticket_repository(self.session, actor).scope)

    async def board(
        self, actor: Actor, space_id: uuid.UUID, filters: Filters, limit: int
    ) -> list[Column]:
        await require(self.session, actor, Action.TICKET_READ, space_id)
        statuses = await status_repository(self.session, actor).in_space(space_id)
        repo = self._repo(actor)
        counts = await repo.column_counts(space_id, filters)
        pages = await repo.first_pages(space_id, filters, limit + 1)
        shown = [v for s in statuses for v in pages.get(s.id, [])[:limit]]
        tagged = {v.ticket.id: v for v in await with_tags(self.session, actor, shown)}
        columns = []
        for status in statuses:
            rows = pages.get(status.id, [])
            items = [tagged[v.ticket.id] for v in rows[:limit]]
            cursor = encode(board_position(items[-1])) if len(rows) > limit else None
            columns.append(Column(status, counts.get(status.id, 0), items, cursor))
        return columns

    async def column(
        self,
        actor: Actor,
        space_id: uuid.UUID,
        status_id: uuid.UUID,
        filters: Filters,
        params: PageParams,
    ) -> pagination.Page[TicketView]:
        await require(self.session, actor, Action.TICKET_READ, space_id)
        status = await status_repository(self.session, actor).get(status_id)
        if status is None or status.space_id != space_id:
            raise status_not_found()
        after = decode(params.cursor) if params.cursor else None
        rows = await self._repo(actor).column(space_id, status_id, filters, after, params.limit + 1)
        items = await with_tags(self.session, actor, rows[: params.limit])
        cursor = encode(board_position(items[-1])) if len(rows) > params.limit else None
        return pagination.Page[TicketView](items=items, next_cursor=cursor)

    async def epics(
        self, actor: Actor, space_id: uuid.UUID, params: PageParams
    ) -> pagination.Page[Epic]:
        await require(self.session, actor, Action.TICKET_READ, space_id)
        after = listing.decode(listing.Sort.NUMBER, params.cursor) if params.cursor else None
        repo = self._repo(actor)
        rows = await repo.epics(space_id, after.number if after else None, params.limit + 1)
        views = await with_tags(self.session, actor, rows[: params.limit])
        children = await repo.children_of([v.ticket.id for v in views])
        items = [Epic(v, children.get(v.ticket.id, {})) for v in views]
        cursor = None
        if len(rows) > params.limit:
            last = listing.Position(0, views[-1].ticket.number)
            cursor = listing.encode(listing.Sort.NUMBER, last)
        return pagination.Page[Epic](items=items, next_cursor=cursor)

    async def assigned_open(self, actor: Actor) -> int:
        """The caller's tickets that are open, active or in review, in the spaces where
        it may still read tickets."""
        return await self._repo(actor).assigned_open(actor.principal.id)
