import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.spaces.schemas import (
    MemberType,
    SpaceCreate,
    SpaceMemberIn,
    SpaceMemberOut,
    SpaceOut,
    SpaceUpdateIn,
)
from app.modules.spaces.service import SpaceService

router = APIRouter(prefix="/spaces", tags=["spaces"])


@router.get("", response_model=Page[SpaceOut])
async def list_spaces(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[SpaceOut]:
    page = await SpaceService(session).list_visible(actor, params)
    return Page[SpaceOut](
        items=[SpaceOut.model_validate(s) for s in page.items], next_cursor=page.next_cursor
    )


@router.post("", response_model=SpaceOut, status_code=201)
async def create_space(body: SpaceCreate, actor: ActorDep, session: SessionDep) -> SpaceOut:
    space = await SpaceService(session).create(
        actor, body.kind, body.name, description=body.description, icon=body.icon
    )
    return SpaceOut.model_validate(space)


@router.get("/{space_id}", response_model=SpaceOut)
async def get_space(space_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> SpaceOut:
    return SpaceOut.model_validate(await SpaceService(session).get(actor, space_id))


@router.patch("/{space_id}", response_model=SpaceOut)
async def update_space(
    space_id: uuid.UUID, body: SpaceUpdateIn, actor: ActorDep, session: SessionDep
) -> SpaceOut:
    space = await SpaceService(session).update(actor, space_id, body, body.version)
    return SpaceOut.model_validate(space)


@router.get("/{space_id}/members", response_model=Page[SpaceMemberOut])
async def list_space_members(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[SpaceMemberOut]:
    page = await SpaceService(session).members(actor, space_id, params)
    return Page[SpaceMemberOut](
        items=[SpaceMemberOut.model_validate(m) for m in page.items],
        next_cursor=page.next_cursor,
    )


@router.put("/{space_id}/members", response_model=SpaceMemberOut)
async def set_space_member(
    space_id: uuid.UUID, body: SpaceMemberIn, actor: ActorDep, session: SessionDep
) -> SpaceMemberOut:
    member = await SpaceService(session).set_member(
        actor, space_id, body.member_type, body.member_id, body.role
    )
    return SpaceMemberOut.model_validate(member)


@router.delete("/{space_id}/members/{member_type}/{member_id}", status_code=204)
async def remove_space_member(
    space_id: uuid.UUID,
    member_type: MemberType,
    member_id: uuid.UUID,
    actor: ActorDep,
    session: SessionDep,
) -> None:
    await SpaceService(session).remove_member(actor, space_id, member_type, member_id)
