import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import AuthDep, SessionDep
from app.modules.users.schemas import UserCreate, UserOut, UserUpdateIn
from app.modules.users.service import UserService

router = APIRouter(prefix="/admin/users", tags=["users"])


@router.get("", response_model=Page[UserOut])
async def list_users(
    params: Annotated[PageParams, Query()], ctx: AuthDep, session: SessionDep
) -> Page[UserOut]:
    page = await UserService(session).list(ctx, params)
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in page.items], next_cursor=page.next_cursor
    )


@router.post("", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, ctx: AuthDep, session: SessionDep) -> UserOut:
    return UserOut.model_validate(await UserService(session).create(ctx, body))


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID, body: UserUpdateIn, ctx: AuthDep, session: SessionDep
) -> UserOut:
    user = await UserService(session).update(ctx, user_id, body, body.version)
    return UserOut.model_validate(user)


@router.post("/{user_id}/deactivate", status_code=204)
async def deactivate_user(user_id: uuid.UUID, ctx: AuthDep, session: SessionDep) -> None:
    await UserService(session).deactivate(ctx, user_id)
