from pydantic import BaseModel, ConfigDict

from app.modules.tickets.models import StatusCategory
from app.modules.tickets.my_board import Card, MyColumn
from app.modules.tickets.schemas import TicketSummaryOut


class MyCardOut(TicketSummaryOut):
    """A ticket on my board, with the name of its space."""

    space_name: str

    @classmethod
    def of_card(cls, card: Card) -> "MyCardOut":
        return cls.model_validate({**cls.fields_of(card.view), "space_name": card.space_name})


class MyColumnOut(BaseModel):
    """A status category: how many of my tickets it holds, the first of them in board
    order (priority, due date with none last, number), and the cursor for more
    (`GET /api/tickets/my-board/{category}`)."""

    category: StatusCategory
    count: int
    items: list[MyCardOut]
    next_cursor: str | None

    @classmethod
    def of(cls, column: MyColumn) -> "MyColumnOut":
        return cls(
            category=column.category,
            count=column.count,
            items=[MyCardOut.of_card(c) for c in column.items],
            next_cursor=column.next_cursor,
        )


class MyBoardOut(BaseModel):
    """My tickets of every space I may read, by category: open, active, review, done
    (done: finished in the last 14 days; cancelled ones are not shown)."""

    columns: list[MyColumnOut]


class MyCardPage(BaseModel):
    items: list[MyCardOut]
    next_cursor: str | None


class MoveCategory(BaseModel):
    """Into the first status of `category` in the ticket's space (422
    `ticket.category_empty` without one); `version` is the ticket version read."""

    model_config = ConfigDict(extra="forbid")

    category: StatusCategory
    version: int
