"""The login session's cookie, set the same way after a password or an OIDC sign-in."""

from fastapi import Request, Response

from app.core.config import Settings


def secure_cookie(request: Request, settings: Settings) -> bool:
    """https as the client saw it (X-Forwarded-Proto from a trusted proxy counts)."""
    return settings.cookie_secure or request.url.scheme == "https"


def set_session_cookie(
    response: Response, request: Request, settings: Settings, token: str
) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=secure_cookie(request, settings),
        samesite="lax",
        path="/",
    )
