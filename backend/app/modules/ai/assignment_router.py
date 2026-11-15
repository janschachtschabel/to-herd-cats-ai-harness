"""AI assignment routes (`ai.manage`; anyone else: 404 `ai.not_found`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.modules.ai.assignment_schemas import (
    AssignmentsOut,
    DefaultIn,
    GroupAssignmentOut,
    GroupsIn,
    PersonalAgentsIn,
    TargetOut,
    UserAssignmentIn,
    UserAssignmentOut,
)
from app.modules.ai.assignments import AssignmentService
from app.modules.auth.deps import ActorDep, SessionDep

assignments = APIRouter(prefix="/ai/assignments", tags=["ai"])


@assignments.get("", response_model=AssignmentsOut)
async def get_assignments(actor: ActorDep, session: SessionDep) -> AssignmentsOut:
    return await _overview(AssignmentService(session), actor)


@assignments.put("/default", response_model=AssignmentsOut)
async def set_default_assignment(
    body: DefaultIn, actor: ActorDep, session: SessionDep
) -> AssignmentsOut:
    service = AssignmentService(session)
    await service.set_default(actor, body.target, body.version)
    return await _overview(service, actor)


@assignments.put("/personal-agents", response_model=AssignmentsOut)
async def set_personal_agents(
    body: PersonalAgentsIn, actor: ActorDep, session: SessionDep
) -> AssignmentsOut:
    """Allow or stop personal agents (`agent.create_personal`), with the version."""
    service = AssignmentService(session)
    await service.set_personal_agents(actor, body.enabled, body.version)
    return await _overview(service, actor)


@assignments.get("/groups", response_model=Page[GroupAssignmentOut])
async def list_group_assignments(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[GroupAssignmentOut]:
    page = await AssignmentService(session).groups(actor, params)
    return Page[GroupAssignmentOut](
        items=[GroupAssignmentOut.of(g) for g in page.items], next_cursor=page.next_cursor
    )


@assignments.put("/groups", response_model=AssignmentsOut)
async def set_group_assignments(
    body: GroupsIn, actor: ActorDep, session: SessionDep
) -> AssignmentsOut:
    """Replace the ordered list (at most 100); names the version of `GET` (409)."""
    service = AssignmentService(session)
    await service.set_groups(actor, body.items, body.version)
    return await _overview(service, actor)


@assignments.get("/users", response_model=Page[UserAssignmentOut])
async def list_user_assignments(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[UserAssignmentOut]:
    page = await AssignmentService(session).users(actor, params)
    return Page[UserAssignmentOut](
        items=[UserAssignmentOut.of(u) for u in page.items], next_cursor=page.next_cursor
    )


@assignments.put("/users/{user_id}", response_model=UserAssignmentOut)
async def set_user_assignment(
    user_id: uuid.UUID, body: UserAssignmentIn, actor: ActorDep, session: SessionDep
) -> UserAssignmentOut:
    named = await AssignmentService(session).set_user(actor, user_id, body.target, body.version)
    return UserAssignmentOut.of(named)


@assignments.delete("/users/{user_id}", status_code=204)
async def remove_user_assignment(
    user_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> None:
    """The person falls back to their groups' or the standard assignment."""
    await AssignmentService(session).remove_user(actor, user_id, version)


async def _overview(service: AssignmentService, actor: Actor) -> AssignmentsOut:
    org, connection_name = await service.overview(actor)
    default = None
    if org is not None and org.connection_id is not None and org.model is not None:
        default = TargetOut(
            connection_id=org.connection_id, connection_name=connection_name or "", model=org.model
        )
    return AssignmentsOut(
        default=default,
        personal_agents=org.personal_agents if org else True,
        version=org.version if org else 1,
    )
