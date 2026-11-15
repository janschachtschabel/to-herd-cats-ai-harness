"""A person's own settings (`PATCH /api/auth/me`): the language, read back by `/auth/me`."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.users.models import User
from tests.factories import PASSWORD, login

ME = "/api/auth/me"


async def test_anyone_logged_in_sets_their_language(guest_client: AsyncClient) -> None:
    me = (await guest_client.get(ME)).json()["user"]
    assert me["locale"] == "de"
    r = await guest_client.patch(ME, json={"locale": "en", "version": me["version"]})
    assert r.status_code == 200, r.text
    assert (r.json()["user"]["locale"], r.json()["user"]["version"]) == ("en", me["version"] + 1)
    assert (await guest_client.get(ME)).json()["user"]["locale"] == "en"


async def test_stale_version_is_a_conflict(member_client: AsyncClient) -> None:
    version = (await member_client.get(ME)).json()["user"]["version"]
    assert (await member_client.patch(ME, json={"locale": "en", "version": version})).is_success
    r = await member_client.patch(ME, json={"locale": "de", "version": version})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "users.version_conflict"


async def test_only_the_language_can_be_set(member_client: AsyncClient) -> None:
    version = (await member_client.get(ME)).json()["user"]["version"]
    for bad in (
        {"locale": "fr", "version": version},
        {"locale": "en"},
        {"locale": "en", "version": version, "system_role": "owner"},
        {"locale": "en", "version": version, "name": "Neu"},
    ):
        assert (await member_client.patch(ME, json=bad)).status_code == 422, bad


async def test_language_change_is_audited(
    member_client: AsyncClient, member, session: AsyncSession
) -> None:
    version = (await member_client.get(ME)).json()["user"]["version"]
    await member_client.patch(ME, json={"locale": "en", "version": version})
    entry = (await session.scalars(select(AuditLog).where(AuditLog.action == "user.updated"))).one()
    assert entry.target_id == member.id
    assert entry.details == {"changes": {"locale": {"from": "de", "to": "en"}}}


PASSWORD_URL = "/api/auth/me/password"


async def test_person_changes_own_password_and_other_sessions_end(
    member: User, make_client, session: AsyncSession
) -> None:
    here = await make_client(csrf=True)
    await login(here, member.email)
    elsewhere = await make_client(csrf=True)
    await login(elsewhere, member.email)
    body = {"current_password": PASSWORD, "new_password": "a-brand-new-password"}
    r = await here.post(PASSWORD_URL, json=body)
    assert r.status_code == 204, r.text
    assert (await here.get(ME)).status_code == 200  # this session stays
    assert (await elsewhere.get(ME)).status_code == 401  # every other one ends
    fresh = await make_client(csrf=True)
    await login(fresh, member.email, "a-brand-new-password")
    entry = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "user.password_changed"))
    ).one()
    assert (entry.actor_id, entry.target_id, entry.details) == (member.id, member.id, None)


async def test_the_current_password_is_required(member_client: AsyncClient) -> None:
    body = {"current_password": "not-my-password", "new_password": "a-brand-new-password"}
    r = await member_client.post(PASSWORD_URL, json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "auth.wrong_password"
    assert (await member_client.get(ME)).status_code == 200  # no logout on a typo


async def test_the_new_password_follows_the_rule(member_client: AsyncClient) -> None:
    for new in ("short", "x" * 201):
        body = {"current_password": PASSWORD, "new_password": new}
        assert (await member_client.post(PASSWORD_URL, json=body)).status_code == 422


async def test_guessing_the_current_password_is_limited(member_client: AsyncClient) -> None:
    body = {"current_password": "not-my-password", "new_password": "a-brand-new-password"}
    codes = [(await member_client.post(PASSWORD_URL, json=body)).status_code for _ in range(6)]
    assert codes == [422] * 5 + [429]
