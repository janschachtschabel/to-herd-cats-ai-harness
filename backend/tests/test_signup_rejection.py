"""Who may sign up, and what a rejection leaves (module review M9a, N4 and the
observation).

- A generic provider signs people up only when "E-Mail vertrauen" (`trust_email`) is
  on, the same rule as linking by address: an untrusted one would take any verified
  address of a listed domain on its word (an IdP where people edit their own
  profile). The administration refuses the combination (422
  `oidc.signup_needs_trust`); Google keeps its `hd` rule.
- Rejecting an account that never was active deletes it with what signing up created
  (identity, personal space, own AI assignment, the managers' notifications) and its
  memberships, so the address is free again; the audit entry keeps ids only.
- Approving or rejecting a waiting account whose role is owner needs an owner, as
  reactivating one does.
"""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.ai.models import UserAssignment
from app.modules.audit.models import AuditLog
from app.modules.groups.models import GroupMember
from app.modules.messaging.notification_models import Notification
from app.modules.oidc.models import UserIdentity
from app.modules.spaces.models import Space, SpaceMember
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories import MakeUser, login
from tests.factories_oidc import PROVIDERS, error_of, make_provider, sign_in
from tests.support.oidc_stub import OidcStub

pytestmark = pytest.mark.usefixtures("oidc_egress")

USERS = "/api/admin/users"
NINA = {"email": "nina@neu.example", "name": "Nina Neu", "sub": "n1"}


async def _signup(owner: AsyncClient, stub: OidcStub, make_client: MakeClient) -> None:
    await make_provider(
        owner, stub, trust_email=True, allow_signup=True, allowed_domains=["neu.example"]
    )
    done = await sign_in(await make_client(), stub, **NINA)
    assert error_of(done) == "oidc.account_pending"


async def _nina(session: AsyncSession) -> User | None:
    return await session.scalar(
        select(User).where(User.email == NINA["email"]).execution_options(populate_existing=True)
    )


async def _count(session: AsyncSession, model: Any, *where: Any) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(*where)) or 0)


async def test_an_untrusted_generic_provider_may_not_sign_people_up(
    owner: AsyncClient, oidc_stub: OidcStub
) -> None:
    body = {
        "kind": "generic",
        "key": "idp",
        "name": "IdP",
        "issuer": oidc_stub.url,
        "client_id": "c",
        "allow_signup": True,
        "allowed_domains": ["neu.example"],
    }
    refused = await owner.post(PROVIDERS, json=body)
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "oidc.signup_needs_trust"
    created = await owner.post(PROVIDERS, json={**body, "allow_signup": False})
    assert created.status_code == 201, created.text
    switched = await owner.patch(
        f"{PROVIDERS}/{created.json()['id']}", json={"version": 1, "allow_signup": True}
    )
    assert switched.status_code == 422
    assert switched.json()["error"]["code"] == "oidc.signup_needs_trust"
    trusted = await owner.patch(
        f"{PROVIDERS}/{created.json()['id']}",
        json={"version": 1, "allow_signup": True, "trust_email": True},
    )
    assert trusted.status_code == 200, trusted.text


async def test_rejecting_a_signup_deletes_the_account_and_frees_the_address(
    owner: AsyncClient,
    owner_user: User,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    session: AsyncSession,
) -> None:
    await _signup(owner, oidc_stub, make_client)
    nina = await _nina(session)
    assert nina is not None
    group = await owner.post("/api/admin/groups", json={"name": "Neue"})
    assert group.status_code == 201, group.text
    added = await owner.post(
        f"/api/admin/groups/{group.json()['id']}/members",
        json={"member_type": "user", "member_id": str(nina.id)},
    )
    assert added.status_code == 204, added.text
    session.add(
        Notification(org_id=nina.org_id, user_id=owner_user.id, account_id=nina.id, reason="signup")
    )
    await session.flush()

    rejected = await owner.post(f"{USERS}/{nina.id}/reject", json={"version": nina.version})
    assert rejected.status_code == 204, rejected.text
    assert await _nina(session) is None
    for model, where in (
        (UserIdentity, UserIdentity.user_id == nina.id),
        (Space, Space.owner_user_id == nina.id),
        (SpaceMember, SpaceMember.member_id == nina.id),
        (GroupMember, GroupMember.member_id == nina.id),
        (UserAssignment, UserAssignment.user_id == nina.id),
        (Notification, Notification.account_id == nina.id),
    ):
        assert await _count(session, model, where) == 0, model.__name__
    audit = await session.scalar(select(AuditLog).where(AuditLog.action == "user.signup_rejected"))
    assert audit is not None and audit.target_id == nina.id
    assert NINA["email"] not in str(audit.details) and NINA["name"] not in str(audit.details)

    # The address is free: the real person can be created, or sign up afresh.
    real = {"email": NINA["email"], "name": "Nina", "password": "lantern-orbit-73-q"}
    created = await owner.post(USERS, json=real)
    assert created.status_code == 201, created.text
    assert (await owner.post(f"{USERS}/{created.json()['id']}/deactivate")).status_code == 204


async def test_a_rejected_person_may_sign_up_again(
    owner: AsyncClient, make_client: MakeClient, oidc_stub: OidcStub, session: AsyncSession
) -> None:
    await _signup(owner, oidc_stub, make_client)
    first = await _nina(session)
    assert first is not None
    assert (
        await owner.post(f"{USERS}/{first.id}/reject", json={"version": first.version})
    ).status_code == 204
    done = await sign_in(await make_client(), oidc_stub, **NINA)
    assert error_of(done) == "oidc.account_pending"
    again = await _nina(session)
    assert again is not None and again.id != first.id


async def test_only_an_owner_decides_on_a_waiting_owner(
    owner: AsyncClient,
    make_client: MakeClient,
    make_user: MakeUser,
    oidc_stub: OidcStub,
    session: AsyncSession,
) -> None:
    await _signup(owner, oidc_stub, make_client)
    nina = await _nina(session)
    assert nina is not None
    made_owner = await owner.patch(
        f"{USERS}/{nina.id}", json={"version": nina.version, "system_role": "owner"}
    )
    assert made_owner.status_code == 200, made_owner.text
    version = made_owner.json()["version"]
    admin_user = await make_user(SystemRole.ADMIN, email="admin@example.com")
    admin = await make_client(csrf=True)
    await login(admin, admin_user.email)
    for verb in ("approve", "reject"):
        refused = await admin.post(f"{USERS}/{nina.id}/{verb}", json={"version": version})
        assert refused.status_code == 403, refused.text
        assert refused.json()["error"]["code"] == "users.owner_only"
    approved = await owner.post(f"{USERS}/{nina.id}/approve", json={"version": version})
    assert approved.status_code == 200, approved.text
