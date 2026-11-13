import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.errors import ValidationFailed
from app.core.pagination import Page, PageParams
from app.core.principal import Principal
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.tickets.listing import Filters, Sort
from app.modules.tickets.models import Priority, StatusCategory, TicketKind
from app.modules.tickets.repository import TicketView
from app.modules.tickets.schemas import (
    AssigneeIn,
    TicketCreate,
    TicketOut,
    TicketSummaryOut,
    TicketUpdate,
)
from app.modules.tickets.service import TicketService, ticket_not_found

space_tickets = APIRouter(prefix="/spaces/{space_id}/tickets", tags=["tickets"])
tickets = APIRouter(prefix="/tickets", tags=["tickets"])

PersonQuery = Annotated[str | None, Query(description="`me` or a person's id")]


def _principal(ref: AssigneeIn | dict[str, Any] | None) -> Principal | None:
    if ref is None:
        return None
    if isinstance(ref, dict):
        ref = AssigneeIn.model_validate(ref)
    return Principal(ref.type, ref.id)


def _person(value: str | None, actor: Actor, name: str) -> uuid.UUID | None:
    """`me`, a person's id, or nothing."""
    if value is None:
        return None
    if value == "me":
        return actor.principal.id
    try:
        return uuid.UUID(value)
    except ValueError:
        raise ValidationFailed(f"{name}: `me` or an id", code="validation_failed") from None


async def _full(session: AsyncSession, actor: Actor, view: TicketView) -> TicketOut:
    children = await TicketService(session).children(actor, view)
    return TicketOut.full(view, children)


@space_tickets.post("", response_model=TicketOut, status_code=201)
async def create_ticket(
    space_id: uuid.UUID, body: TicketCreate, actor: ActorDep, session: SessionDep
) -> TicketOut:
    view = await TicketService(session).create(
        actor,
        space_id,
        title=body.title,
        description_md=body.description_md,
        kind=body.kind,
        status_id=body.status_id,
        priority=body.priority,
        due_on=body.due_on,
        parent_id=body.parent_id,
        assignee=_principal(body.assignee),
    )
    return await _full(session, actor, view)


@tickets.get("", response_model=Page[TicketSummaryOut])
async def list_tickets(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    space_id: uuid.UUID | None = None,
    status_category: Annotated[list[StatusCategory] | None, Query()] = None,
    status_id: uuid.UUID | None = None,
    assignee: PersonQuery = None,
    reporter: PersonQuery = None,
    kind: TicketKind | None = None,
    priority: Priority | None = None,
    parent: Annotated[uuid.UUID | None, Query(description="the parent's id")] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    due_before: date | None = None,
    sort: Sort = Sort.UPDATED,
) -> Page[TicketSummaryOut]:
    """The tickets of every space where the caller may read them."""
    filters = Filters(
        space_id=space_id,
        status_categories=tuple(status_category or ()),
        status_id=status_id,
        assignee_id=_person(assignee, actor, "assignee"),
        reporter_id=_person(reporter, actor, "reporter"),
        kind=kind,
        priority=priority,
        parent_id=parent,
        q=q,
        due_before=due_before,
    )
    page = await TicketService(session).list(actor, filters, sort, params)
    return Page[TicketSummaryOut](
        items=[TicketSummaryOut.of(v) for v in page.items], next_cursor=page.next_cursor
    )


@tickets.get("/{number}", response_model=TicketOut)
async def get_ticket(number: int, actor: ActorDep, session: SessionDep) -> TicketOut:
    view = await TicketService(session).get(actor, _number(number))
    return await _full(session, actor, view)


@tickets.patch("/{number}", response_model=TicketOut)
async def update_ticket(
    number: int, body: TicketUpdate, actor: ActorDep, session: SessionDep
) -> TicketOut:
    values = {name: getattr(body, name) for name in body.model_fields_set if name != "version"}
    if "assignee" in values:
        values["assignee"] = _principal(values["assignee"])
    view = await TicketService(session).update(actor, _number(number), body.version, values)
    return await _full(session, actor, view)


def _number(number: int) -> int:
    """Numbers out of range are no ticket (404, like any free number)."""
    if not 1 <= number < 2**31:
        raise ticket_not_found()
    return number
