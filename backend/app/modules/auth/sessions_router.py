"""`/api/auth/me/sessions`: the caller's own login sessions (J8)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from app.core.errors import Unauthorized
from app.core.pagination import PageParams
from app.modules.auth.cookies import clear_session_cookie
from app.modules.auth.deps import ActorDep, AuthDep, SessionDep, SettingsDep
from app.modules.auth.own_sessions import OwnSessions
from app.modules.auth.schemas import OwnSessionOut, OwnSessionPage

router = APIRouter(prefix="/auth/me/sessions", tags=["auth"])


@router.get("", response_model=OwnSessionPage)
async def list_own_sessions(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    ctx: AuthDep,
    session: SessionDep,
    settings: SettingsDep,
) -> OwnSessionPage:
    """The caller's running sessions, newest first."""
    page = await OwnSessions(session, settings).list(actor, params)
    items = [
        OwnSessionOut(
            id=row.id,
            device=row.device,
            signed_in_at=row.signed_in_at,
            last_used_at=row.last_used_at,
            current=row.id == ctx.session_id,
        )
        for row in page.items
    ]
    return OwnSessionPage(items=items, next_cursor=page.next_cursor)


@router.post("/sign-out-others", status_code=204)
async def sign_out_others(
    actor: ActorDep, ctx: AuthDep, session: SessionDep, settings: SettingsDep
) -> None:
    """Every session of the caller ends but this one."""
    if ctx.session_id is None:
        raise Unauthorized(code="auth.session_invalid")
    await OwnSessions(session, settings).end_others(actor, ctx.session_id)


@router.delete("/{session_id}", status_code=204)
async def end_own_session(
    session_id: uuid.UUID,
    request: Request,
    response: Response,
    actor: ActorDep,
    ctx: AuthDep,
    session: SessionDep,
    settings: SettingsDep,
) -> None:
    """One of the caller's sessions ends (this one too: then the cookie goes)."""
    await OwnSessions(session, settings).end(actor, session_id)
    if session_id == ctx.session_id:
        clear_session_cookie(response, request, settings)
