"""A person with TOTP who signs in through an OIDC provider also gives the second
factor (one way, one strength, ASVS 5.0 V6.3.4): the callback opens no session but
a waiting sign-in, and the sign-in page asks for the code."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.totp.models import SignInChallenge
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories_oidc import make_provider, sign_in
from tests.factories_totp import enroll
from tests.support.clock import SettableClock
from tests.support.oidc_stub import OidcStub

pytestmark = pytest.mark.usefixtures("oidc_egress")


async def test_an_oidc_sign_in_waits_for_the_second_factor(
    owner: AsyncClient,
    member: User,
    member_client: AsyncClient,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    session: AsyncSession,
    totp_time: SettableClock,
) -> None:
    await make_provider(owner, oidc_stub, trust_email=True)
    enrolled = await enroll(member_client, totp_time)
    browser = await make_client(csrf=True)
    back = await sign_in(browser, oidc_stub, email=member.email, sub="s-totp")
    assert back.status_code == 302
    assert back.headers["location"] == "/login?second_factor=totp"
    assert "herd_session" not in back.headers.get("set-cookie", "")
    assert (await browser.get("/api/auth/me")).status_code == 401
    challenge = (await session.scalars(select(SignInChallenge))).one()
    assert (challenge.user_id, challenge.method) == (member.id, "oidc")
    done = await browser.post(
        "/api/auth/login/second-factor", json={"code": enrolled.next_code()}
    )
    assert done.status_code == 200, done.text
    assert (await browser.get("/api/auth/me")).json()["user"]["id"] == str(member.id)


async def test_without_totp_an_oidc_sign_in_opens_the_session(
    owner: AsyncClient, member: User, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    await make_provider(owner, oidc_stub, trust_email=True)
    browser = await make_client(csrf=True)
    back = await sign_in(browser, oidc_stub, email=member.email, sub="s-plain")
    assert back.headers["location"] == "/"
    assert (await browser.get("/api/auth/me")).status_code == 200
