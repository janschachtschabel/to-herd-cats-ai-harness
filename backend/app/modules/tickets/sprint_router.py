import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.tickets.models import SprintState
from app.modules.tickets.sprint_schemas import (
    SprintClose,
    SprintCreate,
    SprintOut,
    SprintStart,
    SprintUpdate,
)
from app.modules.tickets.sprints import SprintService

space_sprints = APIRouter(prefix="/spaces/{space_id}/sprints", tags=["tickets"])
sprints = APIRouter(prefix="/sprints", tags=["tickets"])


@space_sprints.get("", response_model=Page[SprintOut])
async def list_sprints(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    state: Annotated[list[SprintState] | None, Query()] = None,
) -> Page[SprintOut]:
    """The space's sprints: the active one, then the planned ones (earliest start
    first), then the closed ones (latest end first); `state` narrows them."""
    page = await SprintService(session).list(actor, space_id, tuple(state or ()), params)
    return Page[SprintOut](
        items=[SprintOut.of(s) for s in page.items], next_cursor=page.next_cursor
    )


@space_sprints.post("", response_model=SprintOut, status_code=201)
async def create_sprint(
    space_id: uuid.UUID, body: SprintCreate, actor: ActorDep, session: SessionDep
) -> SprintOut:
    sprint = await SprintService(session).create(
        actor,
        space_id,
        name=body.name,
        goal=body.goal,
        starts_on=body.starts_on,
        ends_on=body.ends_on,
    )
    return SprintOut.of(sprint)


@sprints.patch("/{sprint_id}", response_model=SprintOut)
async def update_sprint(
    sprint_id: uuid.UUID, body: SprintUpdate, actor: ActorDep, session: SessionDep
) -> SprintOut:
    values = {name: getattr(body, name) for name in body.model_fields_set if name != "version"}
    sprint = await SprintService(session).update(actor, sprint_id, body.version, values)
    return SprintOut.of(sprint)


@sprints.post("/{sprint_id}/start", response_model=SprintOut)
async def start_sprint(
    sprint_id: uuid.UUID, body: SprintStart, actor: ActorDep, session: SessionDep
) -> SprintOut:
    """Planned → active; 409 `sprint.active_exists` while the space has an active one."""
    return SprintOut.of(await SprintService(session).start(actor, sprint_id, body.version))


@sprints.post("/{sprint_id}/close", response_model=SprintOut)
async def close_sprint(
    sprint_id: uuid.UUID, body: SprintClose, actor: ActorDep, session: SessionDep
) -> SprintOut:
    """Active → closed: unfinished tickets go to the next planned sprint or the
    backlog; the sprint keeps its tally."""
    sprint = await SprintService(session).close(actor, sprint_id, body.version, body.move_open_to)
    return SprintOut.of(sprint)
