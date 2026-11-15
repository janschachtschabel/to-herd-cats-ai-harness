"""The cookies of a sign-in (ASVS 5.0 V3.3): over https, and whenever
HERD_COOKIE_SECURE is set, every cookie is `__Host-`, Secure, HttpOnly, SameSite=Lax,
Path=/ and without Domain, so no other host (a sibling subdomain) can set or overwrite
it; over plain http (a local trial) the names stay plain, because browsers refuse
prefixed cookies there."""

from http.cookies import SimpleCookie

import pytest
from httpx import AsyncClient, Response

from app.core.config import get_settings
from app.core.security import new_session_token
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories import CSRF, PASSWORD
from tests.factories_oidc import make_provider, sign_in, start
from tests.support.oidc_stub import OidcStub


def _cookie(response: Response) -> tuple[str, dict[str, str]]:
    """The one cookie the response sets: its name and its attributes (lower-case)."""
    headers = response.headers.get_list("set-cookie")
    assert len(headers) == 1, headers
    jar: SimpleCookie = SimpleCookie()
    jar.load(headers[0])
    ((name, morsel),) = jar.items()
    flags = {k: str(v).lower() for k, v in morsel.items() if v}
    return name, flags


def _hardened(name: str, flags: dict[str, str], base: str) -> None:
    assert name == f"__Host-{base}"
    assert flags.get("secure") and flags.get("httponly"), flags
    assert flags["samesite"] == "lax" and flags["path"] == "/" and "domain" not in flags


async def _login(browser: AsyncClient, user: User) -> Response:
    body = {"email": user.email, "password": PASSWORD}
    response = await browser.post("/api/auth/login", json=body, headers=CSRF)
    assert response.status_code == 200, response.text
    return response


async def test_cookies_are_httponly_samesite_and_secure_in_production(
    make_client: MakeClient, owner_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Over https and behind a TLS proxy that sends no X-Forwarded-Proto
    (HERD_COOKIE_SECURE=true) alike."""
    browser = await make_client(base_url="https://test")
    name, flags = _cookie(await _login(browser, owner_user))
    _hardened(name, flags, "herd_session")
    assert (await browser.get("/api/auth/me")).status_code == 200
    gone = await browser.post("/api/auth/logout", headers=CSRF)
    name, flags = _cookie(gone)
    assert name == "__Host-herd_session" and flags.get("secure"), flags
    assert (await browser.get("/api/auth/me")).status_code == 401

    monkeypatch.setattr(get_settings(), "cookie_secure", True)
    behind_proxy = await make_client()
    name, flags = _cookie(await _login(behind_proxy, owner_user))
    _hardened(name, flags, "herd_session")


async def test_a_plain_session_cookie_counts_nothing_over_https(
    make_client: MakeClient, owner_user: User
) -> None:
    """A sibling host can set `herd_session` for the parent domain, never
    `__Host-herd_session`: over https only the prefixed one is read."""
    plain = await make_client()
    await _login(plain, owner_user)
    token = plain.cookies["herd_session"]
    assert (await plain.get("/api/auth/me")).status_code == 200
    browser = await make_client(base_url="https://test")
    browser.cookies.set("herd_session", token)
    assert (await browser.get("/api/auth/me")).status_code == 401
    browser.cookies.set("__Host-herd_session", new_session_token())
    assert (await browser.get("/api/auth/me")).status_code == 401


async def test_plain_http_keeps_plain_names(make_client: MakeClient, owner_user: User) -> None:
    name, flags = _cookie(await _login(await make_client(), owner_user))
    assert name == "herd_session" and not flags.get("secure")
    assert flags.get("httponly") and flags["samesite"] == "lax"


@pytest.mark.usefixtures("oidc_egress")
async def test_the_oidc_binding_cookie_is_host_bound_over_https(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    await make_provider(owner, oidc_stub)
    browser = await make_client(base_url="https://test")
    started = await start(browser)
    assert started.status_code == 302
    name, flags = _cookie(started)
    _hardened(name, flags, "herd_oidc")
    assert int(flags["max-age"]) <= 600


async def test_signing_in_again_ends_the_session_it_replaces(
    make_client: MakeClient, owner_user: User
) -> None:
    """ASVS 5.0 V7.2.4: a sign-in issues a new token and ends the one the browser had."""
    browser = await make_client()
    await _login(browser, owner_user)
    old = browser.cookies["herd_session"]
    await _login(browser, owner_user)
    assert browser.cookies["herd_session"] != old
    assert (await browser.get("/api/auth/me")).status_code == 200
    stale = await make_client()
    stale.cookies.set("herd_session", old)
    assert (await stale.get("/api/auth/me")).status_code == 401


@pytest.mark.usefixtures("oidc_egress")
async def test_an_oidc_sign_in_ends_the_session_it_replaces(
    owner: AsyncClient, member: User, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    await make_provider(owner, oidc_stub, trust_email=True)
    browser = await make_client()
    await _login(browser, member)
    old = browser.cookies["herd_session"]
    done = await sign_in(browser, oidc_stub, email=member.email, sub="s-again")
    assert done.headers["location"] == "/"
    stale = await make_client()
    stale.cookies.set("herd_session", old)
    assert (await stale.get("/api/auth/me")).status_code == 401
