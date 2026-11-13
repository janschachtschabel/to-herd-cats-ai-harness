from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.tickets.models import StatusCategory
from app.modules.tickets.my_board import MyBoard
from app.modules.tickets.my_board_schemas import (
    MoveCategory,
    MyBoardOut,
    MyCardOut,
    MyCardPage,
    MyColumnOut,
)
from app.modules.tickets.router import full_ticket, ticket_number
from app.modules.tickets.schemas import TicketOut

my_board = APIRouter(prefix="/tickets/my-board", tags=["tickets"])  # before /tickets/{number}
ticket_moves = APIRouter(prefix="/tickets/{number}", tags=["tickets"])


@my_board.get("", response_model=MyBoardOut)
async def get_my_board(
    actor: ActorDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100, description="tickets per column")] = 50,
) -> MyBoardOut:
    """My tickets of every space where I may read tickets, by status category."""
    columns = await MyBoard(session).board(actor, limit)
    return MyBoardOut(columns=[MyColumnOut.of(c) for c in columns])


@my_board.get("/{category}", response_model=MyCardPage)
async def my_board_column(
    category: StatusCategory,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> MyCardPage:
    """More of one column (its `next_cursor`); `open`, `active`, `review` or `done`."""
    page = await MyBoard(session).column(actor, category, params)
    return MyCardPage(
        items=[MyCardOut.of_card(c) for c in page.items], next_cursor=page.next_cursor
    )


@ticket_moves.post("/move-category", response_model=TicketOut)
async def move_category(
    number: int, body: MoveCategory, actor: ActorDep, session: SessionDep
) -> TicketOut:
    """Into the first status of the category in the ticket's own space (`ticket.edit`)."""
    view = await MyBoard(session).move_category(
        actor, ticket_number(number), body.category, body.version
    )
    return await full_ticket(session, actor, view)
