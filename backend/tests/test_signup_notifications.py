"""A self-registered account waiting for approval tells the user administrators in
their activity view (plan M9 task 5b): everyone who holds `user.manage` now, ids only
in every event."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.notification_models import Notification
from app.modules.users.handlers import notify_on_signup
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories import MakeUser
from tests.factories_dms import People
from tests.factories_oidc import error_of, make_provider, sign_in
from tests.support.oidc_stub import OidcStub

pytestmark = pytest.mark.usefixtures("oidc_egress")

NINA = {"email": "nina@neu.example", "name": "Nina Neu", "sub": "n1"}


async def _signup(people: People, stub: OidcStub, make_client: MakeClient) -> None:
    await make_provider(people.admin, stub, allow_signup=True, allowed_domains=["neu.example"])
    done = await sign_in(await make_client(), stub, **NINA)
    assert error_of(done) == "oidc.account_pending"


async def _deliver(session: AsyncSession) -> None:
    """Hand every `user.signup_pending` so far to the handler (again, if it had them)."""
    rows = await session.scalars(
        select(EventOutbox)
        .where(EventOutbox.type == "user.signup_pending")
        .order_by(EventOutbox.id)
    )
    for row in rows.all():
        await notify_on_signup(session, Event.of(row))


async def _activity(client: AsyncClient) -> list[dict[str, Any]]:
    response = await client.get("/api/activity")
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return [i for i in items if i["reason"] == "signup"]


async def _nina(session: AsyncSession) -> User:
    user = await session.scalar(select(User).where(User.email == NINA["email"]))
    assert user is not None
    return user


async def test_those_who_manage_users_are_told_once_with_ids_only(
    people: People,
    make_user: MakeUser,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    session: AsyncSession,
) -> None:
    gone = await make_user("admin", email="gone-admin@example.com", is_active=False)
    await _signup(people, oidc_stub, make_client)
    await _deliver(session)
    await _deliver(session)  # a second delivery adds nothing
    nina = await _nina(session)
    rows = (
        await session.scalars(select(Notification).where(Notification.account_id.is_not(None)))
    ).all()
    assert sorted(str(n.user_id) for n in rows) == [people.id("admin")]
    assert gone.id not in {n.user_id for n in rows}
    assert {n.reason for n in rows} == {"signup"} and {n.account_id for n in rows} == {nina.id}
    created = (
        await session.scalars(select(EventOutbox).where(EventOutbox.type == "notification.created"))
    ).all()
    assert [e.payload["user_id"] for e in created] == [people.id("admin")]
    text = " ".join(str(e.payload) for e in created)
    assert NINA["email"] not in text and NINA["name"] not in text


async def test_the_activity_names_the_account_and_whether_it_still_waits(
    people: People, make_client: MakeClient, oidc_stub: OidcStub, session: AsyncSession
) -> None:
    await _signup(people, oidc_stub, make_client)
    await _deliver(session)
    nina = await _nina(session)
    (entry,) = await _activity(people.admin)
    assert entry["account"] == {"id": str(nina.id), "awaiting": True}
    assert entry["author"] == {"type": "user", "id": str(nina.id), "name": "Nina Neu"}
    assert entry["conversation"] is None and entry["snippet"] == ""
    assert await _activity(people.alice) == []
    version = nina.version
    approved = await people.admin.post(
        f"/api/admin/users/{nina.id}/approve", json={"version": version}
    )
    assert approved.status_code == 200, approved.text
    (entry,) = await _activity(people.admin)
    assert entry["account"] == {"id": str(nina.id), "awaiting": False}


async def test_someone_who_no_longer_manages_users_no_longer_sees_it(
    people: People,
    owner: AsyncClient,
    make_client: MakeClient,
    oidc_stub: OidcStub,
    session: AsyncSession,
) -> None:
    await _signup(people, oidc_stub, make_client)
    await _deliver(session)
    (entry,) = await _activity(people.admin)
    before = (await people.admin.get("/api/activity/count")).json()
    admin = people.users["admin"]
    demoted = await owner.patch(
        f"/api/admin/users/{admin.id}", json={"version": admin.version, "system_role": "member"}
    )
    assert demoted.status_code == 200, demoted.text
    assert await _activity(people.admin) == []
    after = (await people.admin.get("/api/activity/count")).json()
    assert after["open"] == before["open"] - 1
    done = await people.admin.post(f"/api/activity/{entry['id']}/done")
    assert done.status_code == 404


async def test_an_account_decided_before_delivery_tells_nobody(
    people: People, make_client: MakeClient, oidc_stub: OidcStub, session: AsyncSession
) -> None:
    await _signup(people, oidc_stub, make_client)
    nina = await _nina(session)
    rejected = await people.admin.post(
        f"/api/admin/users/{nina.id}/reject", json={"version": nina.version}
    )
    assert rejected.status_code == 200, rejected.text
    await _deliver(session)
    assert await _activity(people.admin) == []
