"""Signing in through OIDC against the stub (plan M9 task 4): login, link, sign-up,
and every refusal of the callback."""

from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as clocks
from app.core.models_base import utcnow
from app.modules.ai.models import UserAssignment
from app.modules.audit.models import AuditLog
from app.modules.oidc.models import UserIdentity
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories import MakeUser
from tests.factories_dms import People
from tests.factories_oidc import error_of, make_provider, sign_in, start
from tests.support.clock import SettableClock
from tests.support.oidc_stub import OidcStub

pytestmark = pytest.mark.usefixtures("oidc_egress")


async def _me(browser: AsyncClient) -> dict[str, object]:
    response = await browser.get("/api/auth/me")
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


async def test_a_trusted_email_links_and_the_next_sign_in_finds_the_subject(
    owner: AsyncClient,
    member: User,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    session: AsyncSession,
) -> None:
    await make_provider(owner, oidc_stub, trust_email=True)
    browser = await make_client()
    done = await sign_in(browser, oidc_stub, email=member.email.upper(), sub="s-max")
    assert done.status_code == 302 and done.headers["location"] == "/", done.headers
    assert (await _me(browser))["user"]["email"] == member.email  # type: ignore[index]
    identity = await session.scalar(select(UserIdentity).where(UserIdentity.subject == "s-max"))
    assert identity is not None and identity.user_id == member.id
    audit = await session.scalar(select(AuditLog).where(AuditLog.action == "user.identity_linked"))
    assert audit is not None and audit.details == {"provider": "stub", "via": "email"}
    again = await make_client()
    done = await sign_in(again, oidc_stub, email="changed@elsewhere.test", sub="s-max")
    assert done.headers["location"] == "/"
    assert (await _me(again))["user"]["id"] == str(member.id)  # type: ignore[index]


async def test_an_untrusted_email_is_not_linked(
    owner: AsyncClient, member: User, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    await make_provider(owner, oidc_stub)
    done = await sign_in(await make_client(), oidc_stub, email=member.email)
    assert error_of(done) == "oidc.link_refused"
    assert urlsplit(done.headers["location"]).path == "/login"


async def test_a_deactivated_person_is_refused(
    owner: AsyncClient, make_user: MakeUser, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    gone = await make_user(email="gone@example.com", is_active=False)
    await make_provider(owner, oidc_stub, trust_email=True)
    done = await sign_in(await make_client(), oidc_stub, email=gone.email)
    assert error_of(done) == "oidc.account_inactive"


async def test_signup_creates_a_member_without_password_and_without_ai(
    ai_people: People, make_client: MakeClient, oidc_stub: OidcStub, session: AsyncSession
) -> None:
    """The organisation's standard assignment would give `ai.use`; the new person has
    an own "no AI" assignment instead (J2), and once approved signs in without it."""
    assert "ai.use" in (await _me(ai_people.alice))["permissions"]  # type: ignore[operator]
    await make_provider(
        ai_people.admin,
        oidc_stub,
        trust_email=True,
        allow_signup=True,
        allowed_domains=["Neu.Example"],
    )
    identity = {"email": "nina@neu.example", "name": "Nina Neu", "sub": "n1"}
    done = await sign_in(await make_client(), oidc_stub, **identity)
    assert error_of(done) == "oidc.account_pending"  # waits for approval (J2)
    user = await session.scalar(select(User).where(User.email == "nina@neu.example"))
    assert user is not None and user.password_hash is None and not user.is_active
    assignment = await session.get(UserAssignment, user.id)
    assert assignment is not None and assignment.no_ai
    audit = await session.scalar(select(AuditLog).where(AuditLog.action == "user.self_registered"))
    assert audit is not None and audit.actor_id == user.id
    assert audit.details == {"provider": "stub", "system_role": "member"}
    approved = await ai_people.admin.post(
        f"/api/admin/users/{user.id}/approve", json={"version": user.version}
    )
    assert approved.status_code == 200, approved.text
    browser = await make_client()
    done = await sign_in(browser, oidc_stub, **identity)
    assert done.headers["location"] == "/"
    me = await _me(browser)
    assert me["user"]["system_role"] == "member"  # type: ignore[index]
    assert me["user"]["name"] == "Nina Neu"  # type: ignore[index]
    assert me["user"]["locale"] == "de"  # type: ignore[index]
    assert "ai.use" not in me["permissions"]  # type: ignore[operator]
    assert me["ai_model"] is None


async def test_signup_outside_the_domains_is_refused(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub, session: AsyncSession
) -> None:
    await make_provider(
        owner, oidc_stub, trust_email=True, allow_signup=True, allowed_domains=["example.org"]
    )
    for email, code in (
        ("x@sub.example.org", "oidc.domain_not_allowed"),
        ("x@other.test", "oidc.domain_not_allowed"),
    ):
        done = await sign_in(await make_client(), oidc_stub, email=email)
        assert error_of(done) == code
    done = await sign_in(
        await make_client(), oidc_stub, email="x@example.org", email_verified=False
    )
    assert error_of(done) == "oidc.email_unverified"
    assert await session.scalar(select(User).where(User.email.like("x@%"))) is None


async def test_callback_refuses_without_the_binding_cookie(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    """Login CSRF: someone else's callback in this browser finds no flow."""
    await make_provider(owner, oidc_stub, trust_email=True)
    attacker = await make_client()
    query = oidc_stub.state.authorize((await start(attacker)).headers["location"])
    victim = await make_client()
    done = await victim.get("/api/auth/oidc/stub/callback", params=query)
    assert error_of(done) == "oidc.flow_invalid"
    assert "herd_session" not in victim.cookies
    # The right browser can still finish: a stray callback did not use the flow up.
    done = await attacker.get("/api/auth/oidc/stub/callback", params=query)
    assert error_of(done) == "oidc.signup_closed"  # admitted or not, the flow was there


async def test_callback_refuses_a_reused_state(
    owner: AsyncClient, member: User, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    await make_provider(owner, oidc_stub, trust_email=True)
    browser = await make_client()
    started = await start(browser)
    binding = browser.cookies.get("herd_oidc")
    oidc_stub.state.identity["email"] = member.email
    query = oidc_stub.state.authorize(started.headers["location"])
    first = await browser.get("/api/auth/oidc/stub/callback", params=query)
    assert first.headers["location"] == "/"
    browser.cookies.set("herd_oidc", binding, path="/api/auth/oidc")  # type: ignore[arg-type]
    second = await browser.get("/api/auth/oidc/stub/callback", params=query)
    assert error_of(second) == "oidc.flow_invalid"


async def test_callback_refuses_an_expired_flow(
    owner: AsyncClient,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = SettableClock(utcnow())
    monkeypatch.setattr(clocks, "SYSTEM_CLOCK", clock)
    await make_provider(owner, oidc_stub, trust_email=True)
    browser = await make_client()
    query = oidc_stub.state.authorize((await start(browser)).headers["location"])
    clock.advance(timedelta(minutes=10, seconds=1))
    done = await browser.get("/api/auth/oidc/stub/callback", params=query)
    assert error_of(done) == "oidc.flow_invalid"


async def test_callback_refuses_a_flow_of_another_provider(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    await make_provider(owner, oidc_stub, trust_email=True)
    await make_provider(owner, oidc_stub, key="other", name="Other", trust_email=True)
    browser = await make_client()
    query = oidc_stub.state.authorize((await start(browser, "stub")).headers["location"])
    done = await browser.get("/api/auth/oidc/other/callback", params=query)
    assert error_of(done) == "oidc.flow_invalid"


async def test_callback_reports_a_denial_and_a_bad_token(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    await make_provider(owner, oidc_stub, trust_email=True)
    browser = await make_client()
    query = oidc_stub.state.authorize((await start(browser)).headers["location"])
    denied = await browser.get(
        "/api/auth/oidc/stub/callback", params={"state": query["state"], "error": "access_denied"}
    )
    assert error_of(denied) == "oidc.denied"
    for script in ({"alg_mode": "none"}, {"alg_mode": "hs256"}, {"token_claims": {"aud": "x"}}):
        oidc_stub.state.reset()
        for name, value in script.items():
            setattr(oidc_stub.state, name, value)
        done = await sign_in(await make_client(), oidc_stub)
        assert error_of(done) == "oidc.id_token_invalid", script


async def test_an_unknown_or_disabled_provider_sends_back_to_login(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    created = await make_provider(owner, oidc_stub, enabled=False)
    browser = await make_client()
    for key in ("stub", "nope"):
        started = await start(browser, key)
        assert started.status_code == 302
        assert error_of(started) == "oidc.not_found"
    assert created["enabled"] is False


async def test_start_and_callback_are_rate_limited_per_address(
    owner: AsyncClient,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings  # noqa: PLC0415

    monkeypatch.setattr(get_settings(), "oidc_rate_per_minute", 2)
    await make_provider(owner, oidc_stub)
    browser = await make_client()
    assert (await start(browser)).headers["location"].startswith(oidc_stub.url)
    assert (await start(browser)).headers["location"].startswith(oidc_stub.url)
    assert error_of(await start(browser)) == "oidc.rate_limited"


async def test_the_authorization_request_carries_pkce_nonce_and_the_public_callback(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub, public_url: str
) -> None:
    await make_provider(owner, oidc_stub)
    started = await start(await make_client())
    query = {k: v[0] for k, v in parse_qs(urlsplit(started.headers["location"]).query).items()}
    assert query["redirect_uri"] == f"{public_url}/api/auth/oidc/stub/callback"
    assert query["code_challenge_method"] == "S256"
    assert query["scope"] == "openid email profile"
    assert len(query["nonce"]) >= 43 and len(query["state"]) >= 43
    assert "prompt" not in query and "hd" not in query
    cookie = started.headers["set-cookie"]
    assert "herd_oidc=" in cookie and "HttpOnly" in cookie and "Path=/api/auth/oidc" in cookie
    assert "samesite=lax" in cookie.lower()
