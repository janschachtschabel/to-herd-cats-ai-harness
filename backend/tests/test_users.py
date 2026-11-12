from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.auth.models import UserSession
from app.modules.orgs.models import Organization
from app.modules.users.models import User
from tests.factories import login

NEW_USER = {"email": "mia@example.com", "name": "Mia", "password": "mia-password-123"}


async def test_owner_creates_user_and_user_can_login(owner: AsyncClient, make_client) -> None:
    created = await owner.post("/api/admin/users", json=NEW_USER)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["system_role"] == "member" and body["locale"] == "de" and body["version"] == 1
    assert "password" not in body and "password_hash" not in body

    listed = (await owner.get("/api/admin/users")).json()
    assert {u["email"] for u in listed["items"]} == {"owner@example.com", "mia@example.com"}

    mia = await make_client(csrf=True)
    me = await login(mia, NEW_USER["email"], NEW_USER["password"])
    assert me["user"]["name"] == "Mia"


async def test_created_user_can_be_a_guest(owner: AsyncClient) -> None:
    created = await owner.post("/api/admin/users", json={**NEW_USER, "system_role": "guest"})
    assert created.json()["system_role"] == "guest"


async def test_duplicate_email_conflicts(owner: AsyncClient) -> None:
    assert (await owner.post("/api/admin/users", json=NEW_USER)).status_code == 201
    response = await owner.post("/api/admin/users", json={**NEW_USER, "email": "MIA@example.com"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "users.email_taken"


async def test_member_cannot_manage_users(member_client: AsyncClient) -> None:
    assert (await member_client.get("/api/admin/users")).status_code == 403


async def test_member_and_guest_cannot_write_users(
    member_client: AsyncClient, guest_client: AsyncClient, member: User, guest: User
) -> None:
    for client, target in ((member_client, guest), (guest_client, member)):
        for response in (
            await client.get("/api/admin/users"),
            await client.post("/api/admin/users", json=NEW_USER),
            await client.patch(
                f"/api/admin/users/{target.id}", json={"name": "X", "version": target.version}
            ),
            await client.post(f"/api/admin/users/{target.id}/deactivate"),
        ):
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "auth.permission_denied"


async def test_admin_manages_users(make_user, make_client, member: User) -> None:
    admin = await make_user(SystemRole.ADMIN)
    client = await make_client(csrf=True)
    await login(client, admin.email)
    assert (await client.post("/api/admin/users", json=NEW_USER)).status_code == 201
    response = await client.patch(
        f"/api/admin/users/{member.id}", json={"name": "Max M.", "version": member.version}
    )
    assert response.status_code == 200 and response.json()["name"] == "Max M."


async def test_last_owner_cannot_be_demoted_or_deactivated(owner, owner_user):
    r = await owner.patch(
        f"/api/admin/users/{owner_user.id}",
        json={"system_role": "admin", "version": owner_user.version},
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "users.last_owner"
    r = await owner.post(f"/api/admin/users/{owner_user.id}/deactivate")
    assert r.json()["error"]["code"] == "users.last_owner"


async def test_an_owner_can_step_down_when_another_owner_exists(
    owner: AsyncClient, owner_user: User, make_user
) -> None:
    other = await make_user(SystemRole.OWNER)
    r = await owner.patch(
        f"/api/admin/users/{owner_user.id}",
        json={"system_role": "admin", "version": owner_user.version},
    )
    assert r.status_code == 200 and r.json()["system_role"] == "admin"
    # `other` is now the last owner.
    r = await owner.post(f"/api/admin/users/{other.id}/deactivate")
    assert r.status_code == 409


async def test_inactive_owners_do_not_count(owner: AsyncClient, owner_user: User, make_user):
    await make_user(SystemRole.OWNER, is_active=False)
    r = await owner.post(f"/api/admin/users/{owner_user.id}/deactivate")
    assert r.json()["error"]["code"] == "users.last_owner"


async def test_deactivated_user_is_logged_out_immediately(client, owner, member_client, member):
    await owner.post(f"/api/admin/users/{member.id}/deactivate")
    assert (await member_client.get("/api/auth/me")).status_code == 401


async def test_deactivate_deletes_sessions_and_blocks_login(
    owner: AsyncClient, member_client: AsyncClient, member: User, session: AsyncSession, client
) -> None:
    version = member.version
    r = await owner.post(f"/api/admin/users/{member.id}/deactivate")
    assert r.status_code == 204
    count = select(func.count()).select_from(UserSession).where(UserSession.user_id == member.id)
    assert await session.scalar(count) == 0
    listed = (await owner.get("/api/admin/users")).json()["items"]
    row = next(u for u in listed if u["id"] == str(member.id))
    assert row["is_active"] is False and row["version"] == version + 1
    response = await client.post(
        "/api/auth/login",
        json={"email": member.email, "password": "test-password-123"},
        headers={"X-Requested-With": "herd"},
    )
    assert response.status_code == 401


async def test_stale_version_is_409(owner, member):
    r = await owner.patch(
        f"/api/admin/users/{member.id}", json={"name": "X", "version": member.version - 1}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "users.version_conflict"


async def test_version_is_checked_against_the_database(
    owner: AsyncClient, member: User, session: AsyncSession
) -> None:
    """Another request changed the row since this session loaded it."""
    loaded = member.version
    await session.execute(
        update(User).where(User.id == member.id).values(version=User.version + 1),
        execution_options={"synchronize_session": False},
    )
    assert member.version == loaded  # the identity map still holds the old row
    r = await owner.patch(f"/api/admin/users/{member.id}", json={"name": "X", "version": loaded})
    assert r.status_code == 409


async def test_update_changes_fields_and_bumps_version(
    owner: AsyncClient, member: User, make_client
) -> None:
    r = await owner.patch(
        f"/api/admin/users/{member.id}",
        json={
            "name": "Maxi",
            "system_role": "admin",
            "locale": "en",
            "password": "brand-new-password",
            "version": member.version,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["name"], body["system_role"], body["locale"]) == ("Maxi", "admin", "en")
    assert body["version"] == 2
    client = await make_client(csrf=True)
    await login(client, member.email, "brand-new-password")


async def test_update_requires_version(owner: AsyncClient, member: User) -> None:
    r = await owner.patch(f"/api/admin/users/{member.id}", json={"name": "X"})
    assert r.status_code == 422


async def test_list_is_paginated(owner: AsyncClient, make_user) -> None:
    for _ in range(4):
        await make_user()
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        page = (await owner.get("/api/admin/users", params=params)).json()
        assert len(page["items"]) <= 2
        seen += [u["id"] for u in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 5
    assert (await owner.get("/api/admin/users", params={"limit": 101})).status_code == 422
    bad = await owner.get("/api/admin/users", params={"cursor": "garbage"})
    assert bad.status_code == 422


async def test_other_organisations_are_invisible(
    owner: AsyncClient, make_user, session: AsyncSession
) -> None:
    elsewhere = Organization(name="Elsewhere", slug="elsewhere")
    session.add(elsewhere)
    await session.flush()
    stranger = await make_user(organization=elsewhere)
    emails = [u["email"] for u in (await owner.get("/api/admin/users")).json()["items"]]
    assert stranger.email not in emails
    r = await owner.patch(f"/api/admin/users/{stranger.id}", json={"name": "X", "version": 1})
    assert r.status_code == 404 and r.json()["error"]["code"] == "users.not_found"
    r = await owner.post(f"/api/admin/users/{stranger.id}/deactivate")
    assert r.status_code == 404
    # The same address may exist in another organisation.
    created = await owner.post("/api/admin/users", json={**NEW_USER, "email": stranger.email})
    assert created.status_code == 201


async def test_create_validates_input(owner: AsyncClient) -> None:
    for bad in (
        {**NEW_USER, "email": "not-an-email"},
        {**NEW_USER, "password": "short"},
        {**NEW_USER, "locale": "fr"},
        {**NEW_USER, "system_role": "superuser"},
    ):
        assert (await owner.post("/api/admin/users", json=bad)).status_code == 422
