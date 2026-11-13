"""A person's own settings (`PATCH /api/auth/me`): the language, read back by `/auth/me`."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog

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
