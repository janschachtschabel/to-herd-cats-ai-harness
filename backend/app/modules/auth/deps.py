"""FastAPI dependencies: the database session, the caller, and the CSRF header check."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import Forbidden, Unauthorized
from app.core.logging import bind_request_fields, log_context
from app.modules.auth.context import AuthContext
from app.modules.auth.service import AuthService

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "herd"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def current_auth(
    request: Request, session: SessionDep, settings: SettingsDep
) -> AsyncIterator[AuthContext]:
    """The caller, from the session cookie; every log line of the request names them,
    the request line included."""
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise Unauthorized(code="auth.required")
    ctx = await AuthService(session, settings).resolve(token)
    if ctx is None:
        raise Unauthorized(code="auth.session_invalid")
    fields = {"org_id": str(ctx.org_id), "actor": str(ctx.principal)}
    bind_request_fields(**fields)
    with log_context(**fields):
        yield ctx


AuthDep = Annotated[AuthContext, Depends(current_auth)]


async def csrf_guard(request: Request) -> None:
    """Unsafe methods must carry the custom header; browsers never add it cross-site."""
    if request.method in UNSAFE_METHODS:
        if request.headers.get(CSRF_HEADER, "").lower() != CSRF_VALUE:
            raise Forbidden(code="auth.csrf")
