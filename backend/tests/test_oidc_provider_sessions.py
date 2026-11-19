"""Deleting an OIDC provider ends the sessions of the people linked through it (module
review M9a, N5), as unlinking each identity would (ASVS 5.0 V7.4.3): a provider found
compromised is deleted, and nothing opened through it stays signed in. The
administrator who deletes it keeps the session she acts with."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories_oidc import PROVIDERS, make_provider, sign_in
from tests.support.oidc_stub import OidcStub

pytestmark = pytest.mark.usefixtures("oidc_egress")


async def test_deleting_a_provider_ends_the_sessions_of_the_people_linked_through_it(
    owner: AsyncClient,
    owner_user: User,
    member: User,
    member_client: AsyncClient,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    session: AsyncSession,
) -> None:
    created = await make_provider(owner, oidc_stub, trust_email=True)
    browser = await make_client()
    done = await sign_in(browser, oidc_stub, email=member.email, sub="s-member")
    assert done.headers["location"] == "/"
    owners_other = await make_client()
    done = await sign_in(owners_other, oidc_stub, email=owner_user.email, sub="s-owner")
    assert done.headers["location"] == "/"

    gone = await owner.delete(f"{PROVIDERS}/{created['id']}", params={"version": 1})
    assert gone.status_code == 204
    assert (await browser.get("/api/auth/me")).status_code == 401
    assert (await member_client.get("/api/auth/me")).status_code == 401
    assert (await owners_other.get("/api/auth/me")).status_code == 401
    assert (await owner.get("/api/auth/me")).status_code == 200
    audit = await session.scalar(select(AuditLog).where(AuditLog.action == "oidc_provider.deleted"))
    assert audit is not None and audit.details == {"key": "stub", "people": 2}


async def test_deleting_a_provider_leaves_other_people_signed_in(
    owner: AsyncClient, member_client: AsyncClient, oidc_stub: OidcStub
) -> None:
    created = await make_provider(owner, oidc_stub)
    gone = await owner.delete(f"{PROVIDERS}/{created['id']}", params={"version": 1})
    assert gone.status_code == 204
    assert (await member_client.get("/api/auth/me")).status_code == 200
