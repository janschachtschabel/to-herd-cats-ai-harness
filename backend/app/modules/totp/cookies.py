"""The cookie of a sign-in waiting for its second factor: `herd_sign_in`, HttpOnly,
SameSite=Lax, for `CHALLENGE_MINUTES`; on path `/api/auth` over plain http, as
`__Host-herd_sign_in` on path `/` over https (`auth/cookies.py`). It holds the
challenge's random token; the database keeps only its hash."""

from fastapi import Response
from starlette.requests import HTTPConnection

from app.core.config import Settings
from app.modules.auth.cookies import cookie_name, secure_cookie
from app.modules.totp.challenges import CHALLENGE_MINUTES

CHALLENGE_COOKIE = "herd_sign_in"
COOKIE_PATH = "/api/auth"


def _name_and_path(conn: HTTPConnection, settings: Settings) -> tuple[str, str]:
    name = cookie_name(conn, settings, CHALLENGE_COOKIE)
    return name, "/" if name != CHALLENGE_COOKIE else COOKIE_PATH


def challenge_token(conn: HTTPConnection, settings: Settings) -> str | None:
    return conn.cookies.get(_name_and_path(conn, settings)[0]) or None


def set_challenge_cookie(
    response: Response, conn: HTTPConnection, settings: Settings, token: str
) -> None:
    name, path = _name_and_path(conn, settings)
    response.set_cookie(
        name,
        token,
        max_age=CHALLENGE_MINUTES * 60,
        httponly=True,
        secure=secure_cookie(conn, settings),
        samesite="lax",
        path=path,
    )


def clear_challenge_cookie(response: Response, conn: HTTPConnection, settings: Settings) -> None:
    name, path = _name_and_path(conn, settings)
    response.delete_cookie(
        name, path=path, secure=secure_cookie(conn, settings), httponly=True, samesite="lax"
    )
