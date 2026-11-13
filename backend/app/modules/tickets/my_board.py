"""My board (plan M4b decision 4): every ticket assigned to the caller in every space
where it may read tickets, in a column per status category (open, active, review,
done). Done tickets only if their status changed in the last DONE_DAYS days; cancelled
ones never. Each column has its count and first page (board order: priority, due date
with none last, number); `column` pages on. A card names its space.

Moving a ticket to a column (`move_category`, `ticket.edit`, with the version read)
sets the first status (by position) of that category in the ticket's own space; a space
without one answers 422 `ticket.category_empty`. A ticket already in the category stays
where it is. The status is held from the moment it is chosen (as any ticket write
holds its status), so one deleted meanwhile is never set: the next of the category is
chosen, or 422.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Actor
from app.core.errors import ValidationFailed
from app.core.pagination import PageParams
from app.modules.tickets.base import editable, ticket_repository, view_of, with_tags
from app.modules.tickets.models import StatusCategory
from app.modules.tickets.my_board_repository import CATEGORIES, MyBoardRepository
from app.modules.tickets.repository import TicketView
from app.modules.tickets.service import TicketService
from app.modules.tickets.statuses import status_repository
from app.modules.tickets.view_repository import board_position
from app.modules.tickets.views import decode, encode

DONE_DAYS = 14


@dataclass(frozen=True, slots=True)
class Card:
    view: TicketView
    space_name: str


@dataclass(frozen=True, slots=True)
class MyColumn:
    category: StatusCategory
    count: int
    items: list[Card]
    next_cursor: str | None


def done_since(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)) - timedelta(days=DONE_DAYS)


class MyBoard:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _repo(self, actor: Actor) -> MyBoardRepository:
        return MyBoardRepository(self.session, ticket_repository(self.session, actor).scope)

    async def board(self, actor: Actor, limit: int) -> list[MyColumn]:
        repo, me, since = self._repo(actor), actor.principal.id, done_since()
        counts = await repo.my_counts(me, since)
        pages = await repo.my_first_pages(me, since, limit + 1)
        cards = await self._cards(actor, repo, [v for c in CATEGORIES for v in pages[c][:limit]])
        columns = []
        for category in CATEGORIES:
            rows = pages[category]
            items = cards[: len(rows[:limit])]
            cards = cards[len(items) :]
            more = len(rows) > limit
            cursor = encode(board_position(items[-1].view)) if more else None
            columns.append(MyColumn(category, counts.get(category, 0), items, cursor))
        return columns

    async def column(
        self, actor: Actor, category: StatusCategory, params: PageParams
    ) -> pagination.Page[Card]:
        if category not in CATEGORIES:
            raise ValidationFailed("Not a column of the board", code="validation_failed")
        after = decode(params.cursor) if params.cursor else None
        repo = self._repo(actor)
        rows = await repo.my_column(
            actor.principal.id, done_since(), category, after, params.limit + 1
        )
        items = await self._cards(actor, repo, rows[: params.limit])
        more = len(rows) > params.limit
        cursor = encode(board_position(items[-1].view)) if more else None
        return pagination.Page[Card](items=items, next_cursor=cursor)

    async def move_category(
        self, actor: Actor, number: int, category: StatusCategory, version: int
    ) -> TicketView:
        repo, ticket = await editable(self.session, actor, number, version)
        statuses = status_repository(self.session, actor)
        current = await statuses.get(ticket.status_id)
        if current is not None and current.category == category:
            return await view_of(self.session, actor, repo, ticket.id)
        target = await statuses.first_of(ticket.space_id, category)
        if target is None:
            raise ValidationFailed(
                "The ticket's space has no status of this category", code="ticket.category_empty"
            )
        values = {"status_id": target.id}
        return await TicketService(self.session).update(actor, number, version, values)

    async def _cards(
        self, actor: Actor, repo: MyBoardRepository, views: list[TicketView]
    ) -> list[Card]:
        """The views with their tags and their spaces' names (two statements)."""
        tagged = await with_tags(self.session, actor, views)
        names = await repo.space_names({v.ticket.space_id for v in tagged})
        return [Card(v, names.get(v.ticket.space_id, "")) for v in tagged]
