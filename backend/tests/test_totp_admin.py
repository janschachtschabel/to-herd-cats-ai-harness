"""An administrator resets a person's TOTP (a lost device, ASVS 5.0 V6.4.4) with an
audit entry, and sees who has TOTP in the people list."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.audit.models import AuditLog
from app.modules.totp.models import SignInChallenge, UserTotp
from app.modules.users.models import User
from tests.conftest import MakeClient
from tests.factories import CSRF, PASSWORD, MakeUser, login
from tests.factories_totp import enroll
from tests.support.clock import SettableClock


def _reset(user_id: uuid.UUID | str) -> str:
    return f"/api/admin/users/{user_id}/totp/reset"


async def test_an_admin_resets_a_persons_totp(
    owner: AsyncClient,
    member: User,
    member_client: AsyncClient,
    make_client: MakeClient,
    session: AsyncSession,
    totp_time: SettableClock,
) -> None:
    await enroll(member_client, totp_time)
    waiting = await make_client(csrf=True)
    body = {"email": member.email, "password": PASSWORD}
    assert (await waiting.post("/api/auth/login", json=body, headers=CSRF)).status_code == 202
    r = await owner.post(_reset(member.id))
    assert r.status_code == 204, r.text
    assert (await session.scalars(select(UserTotp))).all() == []
    assert (await session.scalars(select(SignInChallenge))).all() == []
    entry = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "user.totp_reset"))
    ).one()
    assert (entry.target_id, entry.details) == (member.id, None)
    fresh = await make_client(csrf=True)
    await login(fresh, member.email)  # the password alone again
    assert (await member_client.get("/api/auth/me/totp")).json()["enabled_at"] is None


async def test_resetting_nothing_changes_nothing(
    owner: AsyncClient, member: User, session: AsyncSession
) -> None:
    assert (await owner.post(_reset(member.id))).status_code == 204
    actions = (await session.scalars(select(AuditLog.action))).all()
    assert "user.totp_reset" not in actions


async def test_only_an_owner_resets_an_owners_totp(
    make_user: MakeUser, make_client: MakeClient, owner_user: User
) -> None:
    admin = await make_user(SystemRole.ADMIN)
    client = await make_client(csrf=True)
    await login(client, admin.email)
    r = await client.post(_reset(owner_user.id))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "users.owner_only"


async def test_people_without_user_manage_cannot_reset(
    member_client: AsyncClient, owner_user: User
) -> None:
    r = await member_client.post(_reset(owner_user.id))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "auth.permission_denied"


async def test_an_unknown_person_answers_404(owner: AsyncClient) -> None:
    r = await owner.post(_reset(uuid.uuid4()))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "users.not_found"


async def test_the_people_list_says_who_has_totp(
    owner: AsyncClient, member: User, member_client: AsyncClient, totp_time: SettableClock
) -> None:
    await enroll(member_client, totp_time)
    items = (await owner.get("/api/admin/users")).json()["items"]
    flags = {item["email"]: item["totp_enabled"] for item in items}
    assert flags[member.email] is True
    assert flags["owner@example.com"] is False
