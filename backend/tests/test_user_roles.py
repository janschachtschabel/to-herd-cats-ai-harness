"""Who may change whom: the owner role, reactivation, and sessions after a reset."""

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.outbox import EventOutbox
from app.core.principal import SystemRole
from app.modules.auth.models import UserSession
from app.modules.users.models import User
from tests.factories import CSRF, PASSWORD, login

NEW_USER = {"email": "mia@example.com", "name": "Mia", "password": "mia-password-123"}


async def _admin_client(make_user, make_client) -> AsyncClient:
    admin = await make_user(SystemRole.ADMIN)
    client = await make_client(csrf=True)
    await login(client, admin.email)
    return client


async def test_password_change_logs_the_person_out(
    owner: AsyncClient, member_client: AsyncClient, member: User, session
) -> None:
    r = await owner.patch(
        f"/api/admin/users/{member.id}",
        json={"password": "brand-new-password", "version": member.version},
    )
    assert r.status_code == 200
    assert (await member_client.get("/api/auth/me")).status_code == 401
    count = select(func.count()).select_from(UserSession).where(UserSession.user_id == member.id)
    assert await session.scalar(count) == 0


async def test_changing_your_own_password_keeps_this_session_only(
    owner: AsyncClient, owner_user: User, make_client
) -> None:
    elsewhere = await make_client(csrf=True)
    await login(elsewhere, owner_user.email)
    r = await owner.patch(
        f"/api/admin/users/{owner_user.id}",
        json={"password": "brand-new-password", "version": owner_user.version},
    )
    assert r.status_code == 200
    assert (await owner.get("/api/auth/me")).status_code == 200
    assert (await elsewhere.get("/api/auth/me")).status_code == 401
    await login(elsewhere, owner_user.email, "brand-new-password")


async def test_other_changes_keep_sessions(
    owner: AsyncClient, member_client: AsyncClient, member: User
) -> None:
    r = await owner.patch(
        f"/api/admin/users/{member.id}", json={"name": "Maxi", "version": member.version}
    )
    assert r.status_code == 200
    assert (await member_client.get("/api/auth/me")).status_code == 200


async def test_reactivate_lets_the_person_log_in_again(
    owner: AsyncClient, member: User, client: AsyncClient
) -> None:
    assert (await owner.post(f"/api/admin/users/{member.id}/deactivate")).status_code == 204
    r = await owner.post(f"/api/admin/users/{member.id}/reactivate")
    assert r.status_code == 204
    row = next(
        u
        for u in (await owner.get("/api/admin/users")).json()["items"]
        if u["id"] == str(member.id)
    )
    assert row["is_active"] is True and row["version"] == 3
    await login(client, member.email)
    # Idempotent: an active person stays as they are.
    assert (await owner.post(f"/api/admin/users/{member.id}/reactivate")).status_code == 204


async def test_reactivate_needs_user_management(
    member_client: AsyncClient, guest: User, owner: AsyncClient
) -> None:
    r = await member_client.post(f"/api/admin/users/{guest.id}/reactivate")
    assert r.status_code == 403
    r = await owner.post("/api/admin/users/0190c0de-0000-7000-8000-000000000000/reactivate")
    assert r.status_code == 404 and r.json()["error"]["code"] == "users.not_found"


async def test_admin_cannot_grant_the_owner_role(make_user, make_client, member: User) -> None:
    admin = await _admin_client(make_user, make_client)
    r = await admin.patch(
        f"/api/admin/users/{member.id}", json={"system_role": "owner", "version": member.version}
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "users.owner_only"
    r = await admin.post("/api/admin/users", json={**NEW_USER, "system_role": "owner"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "users.owner_only"


async def test_admin_cannot_touch_an_owners_role_password_or_activity(
    make_user, make_client, owner_user: User
) -> None:
    await make_user(SystemRole.OWNER)  # so the last-owner rule is not what stops it
    admin = await _admin_client(make_user, make_client)
    target = f"/api/admin/users/{owner_user.id}"
    for response in (
        await admin.patch(target, json={"system_role": "admin", "version": owner_user.version}),
        await admin.patch(
            target, json={"password": "taken-over-password", "version": owner_user.version}
        ),
        await admin.post(f"{target}/deactivate"),
        await admin.post(f"{target}/reactivate"),
    ):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "users.owner_only"
    # Name and language are not privileges.
    r = await admin.patch(target, json={"name": "Olga O.", "version": owner_user.version})
    assert r.status_code == 200


async def test_owner_grants_and_revokes_the_owner_role(owner: AsyncClient, member: User) -> None:
    r = await owner.patch(
        f"/api/admin/users/{member.id}", json={"system_role": "owner", "version": member.version}
    )
    assert r.status_code == 200 and r.json()["system_role"] == "owner"
    r = await owner.patch(
        f"/api/admin/users/{member.id}", json={"system_role": "member", "version": 2}
    )
    assert r.status_code == 200 and r.json()["system_role"] == "member"
    created = await owner.post("/api/admin/users", json={**NEW_USER, "system_role": "owner"})
    assert created.status_code == 201


async def test_admin_still_manages_admins_and_members(
    make_user, make_client, member: User, client: AsyncClient
) -> None:
    admin = await _admin_client(make_user, make_client)
    other_admin = await make_user(SystemRole.ADMIN)
    r = await admin.patch(
        f"/api/admin/users/{other_admin.id}",
        json={"system_role": "member", "version": other_admin.version},
    )
    assert r.status_code == 200
    assert (await admin.post(f"/api/admin/users/{member.id}/deactivate")).status_code == 204
    assert (await admin.post(f"/api/admin/users/{member.id}/reactivate")).status_code == 204
    r = await client.post(
        "/api/auth/login", json={"email": member.email, "password": PASSWORD}, headers=CSRF
    )
    assert r.status_code == 200


async def test_a_role_change_tells_the_person_their_access_changed(
    owner: AsyncClient, member: User, session
) -> None:
    """Member → guest removes rights such as `ai.use`; open clients reload (review M5
    finding 7). A change of name only says nothing."""
    events = select(EventOutbox.type).where(EventOutbox.subject_id == member.id)
    r = await owner.patch(
        f"/api/admin/users/{member.id}", json={"name": "Renamed", "version": member.version}
    )
    assert r.status_code == 200
    assert "access.changed" not in (await session.scalars(events)).all()
    r = await owner.patch(
        f"/api/admin/users/{member.id}",
        json={"system_role": "guest", "version": r.json()["version"]},
    )
    assert r.status_code == 200
    assert list((await session.scalars(events)).all()).count("access.changed") == 1
