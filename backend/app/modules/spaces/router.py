import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.spaces.models import Space
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
    service = SpaceService(session)
    page = await service.list_visible(actor, params)
    roles = await service.my_roles(actor, page.items)
    return Page[SpaceOut](
        items=[SpaceOut.of(s, roles[s.id]) for s in page.items], next_cursor=page.next_cursor
    )


@router.post("", response_model=SpaceOut, status_code=201)
async def create_space(body: SpaceCreate, actor: ActorDep, session: SessionDep) -> SpaceOut:
    service = SpaceService(session)
    space = await service.create(
        actor, body.kind, body.name, description=body.description, icon=body.icon
    )
    return await _out(service, actor, space)


@router.get("/{space_id}", response_model=SpaceOut)
async def get_space(space_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> SpaceOut:
    service = SpaceService(session)
    return await _out(service, actor, await service.get(actor, space_id))


@router.patch("/{space_id}", response_model=SpaceOut)
async def update_space(
    space_id: uuid.UUID, body: SpaceUpdateIn, actor: ActorDep, session: SessionDep
) -> SpaceOut:
    service = SpaceService(session)
    space = await service.update(actor, space_id, body, body.version)
    return await _out(service, actor, space)


@router.get("/{space_id}/members", response_model=Page[SpaceMemberOut])
async def list_space_members(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[SpaceMemberOut]:
    page = await SpaceService(session).members(actor, space_id, params)
    return Page[SpaceMemberOut](
        items=[SpaceMemberOut.of(row) for row in page.items],
        next_cursor=page.next_cursor,
    )


@router.put("/{space_id}/members", response_model=SpaceMemberOut)
async def set_space_member(
    space_id: uuid.UUID, body: SpaceMemberIn, actor: ActorDep, session: SessionDep
) -> SpaceMemberOut:
    member = await SpaceService(session).set_member(
        actor, space_id, body.member_type, body.member_id, body.role
    )
    return SpaceMemberOut.of(member)


@router.delete("/{space_id}/members/{member_type}/{member_id}", status_code=204)
async def remove_space_member(
    space_id: uuid.UUID,
    member_type: MemberType,
    member_id: uuid.UUID,
    actor: ActorDep,
    session: SessionDep,
) -> None:
    await SpaceService(session).remove_member(actor, space_id, member_type, member_id)


async def _out(service: SpaceService, actor: Actor, space: Space) -> SpaceOut:
    roles = await service.my_roles(actor, [space])
    return SpaceOut.of(space, roles[space.id])
