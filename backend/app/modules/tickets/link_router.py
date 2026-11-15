import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.tickets.links import TicketLinks
from app.modules.tickets.router import ticket_number
from app.modules.tickets.schemas import LinkedPageOut, TicketSummaryOut

ticket_pages = APIRouter(prefix="/tickets/{number}/pages", tags=["tickets"])
page_tickets = APIRouter(prefix="/pages/{page_id}/tickets", tags=["tickets"])


@ticket_pages.get("", response_model=Page[LinkedPageOut])
async def list_ticket_pages(
    number: int, params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[LinkedPageOut]:
    """The pages the ticket links that the caller sees, last linked first."""
    page = await TicketLinks(session).pages_of(actor, ticket_number(number), params)
    return Page[LinkedPageOut](
        items=[LinkedPageOut.of(p) for p in page.items], next_cursor=page.next_cursor
    )


@ticket_pages.put("/{page_id}", status_code=204)
async def link_page(number: int, page_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    """Link a page the caller sees, of any space (`ticket.edit`); linking again
    changes nothing."""
    await TicketLinks(session).link(actor, ticket_number(number), page_id)


@ticket_pages.delete("/{page_id}", status_code=204)
async def unlink_page(
    number: int, page_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> None:
    """Remove the link to a page the caller sees (`ticket.edit`); 204 also when there
    was none."""
    await TicketLinks(session).unlink(actor, ticket_number(number), page_id)


@page_tickets.get("", response_model=Page[TicketSummaryOut])
async def list_page_tickets(
    page_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[TicketSummaryOut]:
    """The tickets linking the page that the caller may see, newest first."""
    page = await TicketLinks(session).tickets_of(actor, page_id, params)
    return Page[TicketSummaryOut](
        items=[TicketSummaryOut.of(v) for v in page.items], next_cursor=page.next_cursor
    )
