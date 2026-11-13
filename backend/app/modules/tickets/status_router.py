import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.tickets.status_schemas import StatusCreate, StatusOut, StatusUpdate
from app.modules.tickets.statuses import StatusService

space_statuses = APIRouter(prefix="/spaces/{space_id}/ticket-statuses", tags=["tickets"])
statuses = APIRouter(prefix="/ticket-statuses", tags=["tickets"])


@space_statuses.get("", response_model=Page[StatusOut])
async def list_statuses(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[StatusOut]:
    """The space's statuses in order."""
    page = await StatusService(session).list(actor, space_id, params)
    return Page[StatusOut](
        items=[StatusOut.of(s) for s in page.items], next_cursor=page.next_cursor
    )


@space_statuses.post("", response_model=StatusOut, status_code=201)
async def create_status(
    space_id: uuid.UUID, body: StatusCreate, actor: ActorDep, session: SessionDep
) -> StatusOut:
    status = await StatusService(session).create(
        actor, space_id, body.name, body.category, body.position
    )
    return StatusOut.of(status)


@statuses.patch("/{status_id}", response_model=StatusOut)
async def update_status(
    status_id: uuid.UUID, body: StatusUpdate, actor: ActorDep, session: SessionDep
) -> StatusOut:
    status = await StatusService(session).update(
        actor,
        status_id,
        body.version,
        name=body.name,
        category=body.category,
        position=body.position,
    )
    return StatusOut.of(status)


@statuses.delete("/{status_id}", status_code=204)
async def delete_status(
    status_id: uuid.UUID,
    version: Annotated[int, Query(description="the version read")],
    actor: ActorDep,
    session: SessionDep,
    replace_with: Annotated[
        uuid.UUID | None, Query(description="another status of the space, for its tickets")
    ] = None,
) -> None:
    await StatusService(session).delete(actor, status_id, version, replace_with)
