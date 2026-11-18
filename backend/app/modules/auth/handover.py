"""A sign-in hands its new session to the browser, the same way for a password, an
OIDC provider and the second factor: the session the browser had ends (ASVS 5.0
V7.2.4), the new one notes its device hint (J8), the cookie is set."""

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_token
from app.modules.auth.cookies import session_token, set_session_cookie
from app.modules.auth.device import device_hint
from app.modules.auth.service import AuthService


async def hand_over(
    session: AsyncSession, settings: Settings, request: Request, response: Response, token: str
) -> None:
    service = AuthService(session, settings)
    await service.end_replaced(session_token(request, settings))
    hint = device_hint(request.headers.get("user-agent"))
    await service.sessions.note_device(hash_token(token), hint)
    set_session_cookie(response, request, settings, token)
