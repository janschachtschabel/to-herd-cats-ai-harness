import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.tickets.listing import Filters
from app.modules.tickets.models import TicketKind
from app.modules.tickets.router import PersonQuery, SprintQuery, TagQuery, person, sprint_filter
from app.modules.tickets.schemas import TicketSummaryOut
from app.modules.tickets.view_schemas import BoardColumnOut, BoardOut, EpicOut, TicketCountsOut
from app.modules.tickets.views import TicketViews

space_views = APIRouter(prefix="/spaces/{space_id}", tags=["tickets"])
ticket_counts = APIRouter(prefix="/tickets", tags=["tickets"])  # before /tickets/{number}

EpicQuery = Annotated[
    uuid.UUID | None, Query(description="only an epic's children and their children")
]


def _filters(
    actor: Actor,
    assignee: str | None,
    kind: TicketKind | None,
    tag: list[uuid.UUID] | None,
    epic: uuid.UUID | None,
    sprint: str | None,
) -> Filters:
    return Filters(
        assignee_id=person(assignee, actor, "assignee"),
        kind=kind,
        tag_ids=tuple(dict.fromkeys(tag or ())),
        epic_id=epic,
        **sprint_filter(sprint),
    )


@space_views.get("/board", response_model=BoardOut)
async def board(
    space_id: uuid.UUID,
    actor: ActorDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100, description="tickets per column")] = 50,
    assignee: PersonQuery = None,
    kind: TicketKind | None = None,
    tag: TagQuery = None,
    epic: EpicQuery = None,
    sprint: SprintQuery = None,
) -> BoardOut:
    """The space's statuses in order, each with its count and first tickets."""
    filters = _filters(actor, assignee, kind, tag, epic, sprint)
    columns = await TicketViews(session).board(actor, space_id, filters, limit)
    return BoardOut(columns=[BoardColumnOut.of(c) for c in columns])


@space_views.get("/board/{status_id}", response_model=Page[TicketSummaryOut])
async def board_column(
    space_id: uuid.UUID,
    status_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    assignee: PersonQuery = None,
    kind: TicketKind | None = None,
    tag: TagQuery = None,
    epic: EpicQuery = None,
    sprint: SprintQuery = None,
) -> Page[TicketSummaryOut]:
    """More of one column, in board order (the column's `next_cursor`)."""
    filters = _filters(actor, assignee, kind, tag, epic, sprint)
    page = await TicketViews(session).column(actor, space_id, status_id, filters, params)
    return Page[TicketSummaryOut](
        items=[TicketSummaryOut.of(v) for v in page.items], next_cursor=page.next_cursor
    )


@space_views.get("/epics", response_model=Page[EpicOut])
async def epics(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[EpicOut]:
    """The space's epics, newest first, with their progress; an epic's children come
    from the list (`parent`)."""
    page = await TicketViews(session).epics(actor, space_id, params)
    return Page[EpicOut](
        items=[EpicOut.from_epic(e) for e in page.items], next_cursor=page.next_cursor
    )


@ticket_counts.get("/counts", response_model=TicketCountsOut)
async def counts(actor: ActorDep, session: SessionDep) -> TicketCountsOut:
    return TicketCountsOut(assigned_open=await TicketViews(session).assigned_open(actor))
