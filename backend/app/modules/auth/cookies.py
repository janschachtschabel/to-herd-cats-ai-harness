"""The cookies of a sign-in: the login session's, set the same way after a password or
an OIDC sign-in, and read the same way by every route, the live stream and the collab
relay.

Over https (and whenever `HERD_COOKIE_SECURE` is set) a cookie's name gets the
`__Host-` prefix (ASVS 5.0 V3.3.1, V3.3.3): browsers keep such a cookie only when it is
Secure, has Path=/ and no Domain, so no other host (a sibling subdomain) can set or
overwrite it, and only the prefixed name is read there. Over plain http (a local trial)
browsers refuse prefixed cookies, so the name stays plain.
"""

from fastapi import Response
from starlette.requests import HTTPConnection

from app.core.config import Settings

HOST_PREFIX = "__Host-"
_PREFIXES = (HOST_PREFIX, "__Secure-")


def secure_cookie(conn: HTTPConnection, settings: Settings) -> bool:
    """https as the client saw it (X-Forwarded-Proto from a trusted proxy counts)."""
    return settings.cookie_secure or conn.url.scheme in ("https", "wss")


def cookie_name(conn: HTTPConnection, settings: Settings, name: str) -> str:
    """`name` as this connection sets and reads it: `__Host-<name>` when secure."""
    if not secure_cookie(conn, settings) or name.startswith(_PREFIXES):
        return name
    return HOST_PREFIX + name


def session_cookie_name(conn: HTTPConnection, settings: Settings) -> str:
    return cookie_name(conn, settings, settings.session_cookie_name)


def session_token(conn: HTTPConnection, settings: Settings) -> str | None:
    """The login session's token from the cookie this connection may use, or None."""
    return conn.cookies.get(session_cookie_name(conn, settings)) or None


def set_session_cookie(
    response: Response, conn: HTTPConnection, settings: Settings, token: str
) -> None:
    response.set_cookie(
        session_cookie_name(conn, settings),
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=secure_cookie(conn, settings),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, conn: HTTPConnection, settings: Settings) -> None:
    response.delete_cookie(
        session_cookie_name(conn, settings),
        path="/",
        secure=secure_cookie(conn, settings),
        httponly=True,
        samesite="lax",
    )
