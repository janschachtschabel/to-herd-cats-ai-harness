import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.core.principal import Principal, PrincipalType
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.groups.schemas import (
    GroupCreate,
    GroupMemberIn,
    GroupMemberOut,
    GroupOut,
    GroupUpdateIn,
)
from app.modules.groups.service import GroupService

router = APIRouter(prefix="/admin/groups", tags=["groups"])


@router.get("", response_model=Page[GroupOut])
async def list_groups(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[GroupOut]:
    page = await GroupService(session).list(actor, params)
    return Page[GroupOut](
        items=[GroupOut.model_validate(g) for g in page.items], next_cursor=page.next_cursor
    )


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(body: GroupCreate, actor: ActorDep, session: SessionDep) -> GroupOut:
    return GroupOut.model_validate(await GroupService(session).create(actor, body))


@router.get("/{group_id}", response_model=GroupOut)
async def get_group(group_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> GroupOut:
    return GroupOut.model_validate(await GroupService(session).get(actor, group_id))


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: uuid.UUID, body: GroupUpdateIn, actor: ActorDep, session: SessionDep
) -> GroupOut:
    group = await GroupService(session).update(actor, group_id, body, body.version)
    return GroupOut.model_validate(group)


@router.delete("/{group_id}", status_code=204)
async def delete_group(group_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await GroupService(session).delete(actor, group_id)


@router.get("/{group_id}/members", response_model=Page[GroupMemberOut])
async def list_group_members(
    group_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[GroupMemberOut]:
    page = await GroupService(session).members(actor, group_id, params)
    return Page[GroupMemberOut](
        items=[GroupMemberOut.model_validate(m) for m in page.items],
        next_cursor=page.next_cursor,
    )


@router.post("/{group_id}/members", status_code=204)
async def add_group_member(
    group_id: uuid.UUID, body: GroupMemberIn, actor: ActorDep, session: SessionDep
) -> None:
    principal = Principal(body.member_type, body.member_id)
    await GroupService(session).add_member(actor, group_id, principal)


@router.delete("/{group_id}/members/{member_type}/{member_id}", status_code=204)
async def remove_group_member(
    group_id: uuid.UUID,
    member_type: Literal[PrincipalType.USER],
    member_id: uuid.UUID,
    actor: ActorDep,
    session: SessionDep,
) -> None:
    principal = Principal(member_type, member_id)
    await GroupService(session).remove_member(actor, group_id, principal)
