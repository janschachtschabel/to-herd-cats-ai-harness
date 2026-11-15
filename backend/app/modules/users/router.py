import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, AuthDep, SessionDep
from app.modules.users.schemas import (
    PendingCountOut,
    SignupDecisionIn,
    UserCreate,
    UserOut,
    UserUpdateIn,
)
from app.modules.users.service import UserService

router = APIRouter(prefix="/admin/users", tags=["users"])


@router.get("", response_model=Page[UserOut])
async def list_users(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    pending: Annotated[bool, Query(description="true: only accounts awaiting approval")] = False,
) -> Page[UserOut]:
    page = await UserService(session).list(actor, params, pending=pending)
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in page.items], next_cursor=page.next_cursor
    )


@router.get("/pending/count", response_model=PendingCountOut)
async def count_pending(actor: ActorDep, session: SessionDep) -> PendingCountOut:
    """How many self-registered accounts wait for approval (the admin navigation's badge)."""
    return PendingCountOut(count=await UserService(session).count_pending(actor))


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


@router.post("/{user_id}/sign-out", status_code=204)
async def sign_out_user(
    user_id: uuid.UUID, actor: ActorDep, ctx: AuthDep, session: SessionDep
) -> None:
    """Ends every session of the person; they stay active and may sign in again."""
    await UserService(session).sign_out(actor, user_id, current_session=ctx.session_id)


@router.post("/{user_id}/deactivate", status_code=204)
async def deactivate_user(user_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await UserService(session).deactivate(actor, user_id)


@router.post("/{user_id}/reactivate", status_code=204)
async def reactivate_user(user_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await UserService(session).reactivate(actor, user_id)


@router.post("/{user_id}/approve", response_model=UserOut)
async def approve_signup(
    user_id: uuid.UUID, body: SignupDecisionIn, actor: ActorDep, session: SessionDep
) -> UserOut:
    """Let a self-registered account in (409 `users.not_pending` once decided)."""
    service = UserService(session)
    user = await service.decide_signup(actor, user_id, body.version, approve=True)
    return UserOut.model_validate(user)


@router.post("/{user_id}/reject", response_model=UserOut)
async def reject_signup(
    user_id: uuid.UUID, body: SignupDecisionIn, actor: ActorDep, session: SessionDep
) -> UserOut:
    """Refuse a self-registered account: it stays deactivated."""
    service = UserService(session)
    user = await service.decide_signup(actor, user_id, body.version, approve=False)
    return UserOut.model_validate(user)
