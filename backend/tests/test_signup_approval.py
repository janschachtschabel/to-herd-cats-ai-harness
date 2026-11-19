"""Self-registration waits for an admin's approval (plan M9 task 5b, Jan's answer J2):
the account is created inactive and awaiting approval, nobody is signed in, and only
"Freigeben" lets the person in ("Ablehnen" deletes the account:
`test_signup_rejection.py`)."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.modules.audit.models import AuditLog
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories import MakeUser
from tests.factories_oidc import error_of, make_provider, sign_in
from tests.support.oidc_stub import OidcStub

pytestmark = pytest.mark.usefixtures("oidc_egress")

USERS = "/api/admin/users"
NINA = {"email": "nina@neu.example", "name": "Nina Neu", "sub": "n1"}


async def _signup(owner: AsyncClient, stub: OidcStub, make_client: MakeClient) -> AsyncClient:
    await make_provider(
        owner, stub, trust_email=True, allow_signup=True, allowed_domains=["neu.example"]
    )
    browser = await make_client()
    done = await sign_in(browser, stub, **NINA)
    assert error_of(done) == "oidc.account_pending", done.headers
    return browser


async def _nina(session: AsyncSession) -> User:
    user = await session.scalar(
        select(User).where(User.email == NINA["email"]).execution_options(populate_existing=True)
    )
    assert user is not None
    return user


async def _pending(owner: AsyncClient) -> list[dict[str, Any]]:
    response = await owner.get(USERS, params={"pending": "true"})
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def _decide(owner: AsyncClient, user_id: object, verb: str, version: int) -> Any:
    return await owner.post(f"{USERS}/{user_id}/{verb}", json={"version": version})


async def test_signup_creates_an_inactive_account_awaiting_approval_and_no_session(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub, session: AsyncSession
) -> None:
    browser = await _signup(owner, oidc_stub, make_client)
    assert (await browser.get("/api/auth/me")).status_code == 401
    user = await _nina(session)
    assert not user.is_active and user.awaiting_approval_since is not None
    assert user.system_role == "member" and user.password_hash is None
    audit = await session.scalar(select(AuditLog).where(AuditLog.action == "user.self_registered"))
    assert audit is not None and audit.actor_id == user.id
    event = await session.scalar(
        select(EventOutbox).where(EventOutbox.type == "user.signup_pending")
    )
    assert event is not None and event.subject_id == user.id
    assert event.payload == {"user_id": str(user.id)}  # ids only: no address, no name


async def test_signing_in_again_while_waiting_says_so(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub
) -> None:
    await _signup(owner, oidc_stub, make_client)
    again = await make_client()
    done = await sign_in(again, oidc_stub, **NINA)
    assert error_of(done) == "oidc.account_pending"
    assert (await again.get("/api/auth/me")).status_code == 401


async def test_admins_list_and_count_the_waiting_accounts(
    owner: AsyncClient,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    make_user: MakeUser,
    session: AsyncSession,
) -> None:
    await make_user(email="gone@example.com", is_active=False)  # deactivated: not waiting
    assert (await owner.get(f"{USERS}/pending/count")).json() == {"count": 0}
    await _signup(owner, oidc_stub, make_client)
    user = await _nina(session)
    waiting = await _pending(owner)
    assert [u["email"] for u in waiting] == [NINA["email"]]
    assert waiting[0]["awaiting_approval_since"] is not None
    assert waiting[0]["is_active"] is False
    assert (await owner.get(f"{USERS}/pending/count")).json() == {"count": 1}
    everyone = (await owner.get(USERS)).json()["items"]
    assert str(user.id) in {u["id"] for u in everyone}


async def test_approving_lets_the_person_in_as_a_member(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub, session: AsyncSession
) -> None:
    await _signup(owner, oidc_stub, make_client)
    user = await _nina(session)
    version = user.version  # the shared session's object follows the change
    response = await _decide(owner, user.id, "approve", version)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_active"] is True and body["awaiting_approval_since"] is None
    assert body["system_role"] == "member" and body["version"] == version + 1
    audit = await session.scalar(select(AuditLog).where(AuditLog.action == "user.signup_approved"))
    assert audit is not None and audit.target_id == user.id
    assert await _pending(owner) == []
    browser = await make_client()
    done = await sign_in(browser, oidc_stub, **NINA)
    assert done.headers["location"] == "/", done.headers
    me = (await browser.get("/api/auth/me")).json()
    assert me["user"]["email"] == NINA["email"] and me["user"]["system_role"] == "member"
    assert "user.manage" not in me["permissions"]


async def test_deciding_races_answer_409(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub, session: AsyncSession
) -> None:
    await _signup(owner, oidc_stub, make_client)
    user = await _nina(session)
    version = user.version
    stale = await _decide(owner, user.id, "reject", version - 1)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "users.version_conflict"
    assert (await _decide(owner, user.id, "approve", version)).status_code == 200
    again = await _decide(owner, user.id, "reject", version + 1)
    assert again.status_code == 409 and again.json()["error"]["code"] == "users.not_pending"


async def test_a_waiting_account_is_approved_not_reactivated(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub, session: AsyncSession
) -> None:
    """Reactivating would let the person in without the approval's audit entry."""
    await _signup(owner, oidc_stub, make_client)
    user = await _nina(session)
    response = await owner.post(f"{USERS}/{user.id}/reactivate")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "users.awaiting_approval"
    assert not (await _nina(session)).is_active


async def test_only_user_managers_decide(
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    session: AsyncSession,
) -> None:
    await _signup(owner, oidc_stub, make_client)
    user = await _nina(session)
    for path in (f"{USERS}/{user.id}/approve", f"{USERS}/{user.id}/reject"):
        response = await member_client.post(path, json={"version": user.version})
        assert response.status_code == 403, response.text
    assert (await member_client.get(f"{USERS}/pending/count")).status_code == 403
    assert (await member_client.get(USERS, params={"pending": "true"})).status_code == 403
    unknown = await _decide(owner, "00000000-0000-0000-0000-000000000000", "approve", 1)
    assert unknown.status_code == 404
    other = await _decide(owner, member.id, "approve", member.version)
    assert other.status_code == 409 and other.json()["error"]["code"] == "users.not_pending"
