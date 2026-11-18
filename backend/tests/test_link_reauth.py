"""Linking a new sign-in account needs the password again, or a sign-in through a
provider of this very session at most 10 minutes old (ASVS 5.0 V7.5.1, plan M9 task
18, J9)."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories import PASSWORD
from tests.factories_oidc import make_provider, sign_in
from tests.support.clock import SettableClock
from tests.support.oidc_stub import OidcStub

pytestmark = pytest.mark.usefixtures("oidc_egress")
LINK = "/api/auth/me/identities/stub/link"


def _refused(answer: object, status: int, code: str) -> None:
    assert answer.status_code == status, answer.text  # type: ignore[attr-defined]
    assert answer.json()["error"]["code"] == code  # type: ignore[attr-defined]


async def test_linking_needs_a_password_or_a_fresh_sign_in(
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    session: AsyncSession,
    session_time: SettableClock,
) -> None:
    await make_provider(owner, oidc_stub, trust_email=True)
    # Signed in with the password: the running session alone is not enough.
    _refused(await member_client.post(LINK), 403, "auth.reauth_required")
    _refused(await member_client.post(LINK, json={}), 403, "auth.reauth_required")
    _refused(
        await member_client.post(LINK, json={"password": "not-her-password"}),
        422,
        "auth.wrong_password",
    )
    started = await member_client.post(LINK, json={"password": PASSWORD})
    assert started.status_code == 200, started.text
    assert started.json()["url"].startswith(oidc_stub.url)

    # Signed in through a provider just now: no password needed, for 10 minutes.
    member.password_hash = None
    await session.flush()
    federated = await make_client(csrf=True)
    done = await sign_in(federated, oidc_stub, email=member.email, sub="max-sub")
    assert done.headers["location"] == "/"
    assert (await federated.post(LINK)).status_code == 200
    session_time.advance(timedelta(minutes=10, seconds=1))
    _refused(await federated.post(LINK), 403, "auth.reauth_required")


async def test_wrong_passwords_before_linking_are_limited(
    owner: AsyncClient, member_client: AsyncClient, oidc_stub: OidcStub
) -> None:
    await make_provider(owner, oidc_stub)
    for _ in range(5):
        _refused(
            await member_client.post(LINK, json={"password": "x" * 12}), 422, "auth.wrong_password"
        )
    _refused(
        await member_client.post(LINK, json={"password": PASSWORD}), 429, "auth.too_many_attempts"
    )
