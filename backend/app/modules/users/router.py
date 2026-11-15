import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, AuthDep, SessionDep
from app.modules.users.schemas import UserCreate, UserOut, UserUpdateIn
from app.modules.users.service import UserService

router = APIRouter(prefix="/admin/users", tags=["users"])


@router.get("", response_model=Page[UserOut])
async def list_users(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[UserOut]:
    page = await UserService(session).list(actor, params)
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in page.items], next_cursor=page.next_cursor
    )


@router.post("", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, actor: ActorDep, session: SessionDep) -> UserOut:
    return UserOut.model_validate(await UserService(session).create(actor, body))


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID, body: UserUpdateIn, actor: ActorDep, ctx: AuthDep, session: SessionDep
) -> UserOut:
    user = await UserService(session).update(
        actor, user_id, body, body.version, current_session=ctx.session_id
    )
    return UserOut.model_validate(user)


@router.post("/{user_id}/deactivate", status_code=204)
async def deactivate_user(user_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await UserService(session).deactivate(actor, user_id)


@router.post("/{user_id}/reactivate", status_code=204)
async def reactivate_user(user_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await UserService(session).reactivate(actor, user_id)
