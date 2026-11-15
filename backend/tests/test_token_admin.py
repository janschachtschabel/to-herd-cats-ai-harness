"""Plan M8 task 1 (decisions 4 and 5): the organisation's MCP switch and data location
(`/api/ai/mcp`, `ai.manage`, audited) and the admins' view of every token (metadata
only: never a hash or clear text) with revoking any of them (audited). Without
`ai.manage`: 404 `ai.not_found`, as for the rest of the AI administration."""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.modules.audit.models import AuditLog
from app.modules.orgs.models import Organization
from app.modules.tokens.models import AccessToken, TokenKind, TokenMode
from app.modules.users.models import User
from tests.factories import MakeUser
from tests.factories_tokens import mcp_on, new_token


async def test_the_switch_is_off_until_an_admin_turns_it_on(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    guest_client: AsyncClient,
    member: User,
) -> None:
    shown = (await owner.get("/api/ai/mcp")).json()
    assert shown == {"enabled": False, "data_location": "external", "version": 1}
    assert "mcp.use" not in (await owner.get("/api/auth/me")).json()["permissions"]
    turned = await mcp_on(owner, data_location="eu")
    assert turned == {"enabled": True, "data_location": "eu", "version": 2}
    for client, holds in ((owner, True), (member_client, True), (guest_client, False)):
        permissions = (await client.get("/api/auth/me")).json()["permissions"]
        assert ("mcp.use" in permissions) is holds
    (entry,) = await session.scalars(select(AuditLog).where(AuditLog.action == "mcp.settings_set"))
    assert entry.target_type == "organization" and entry.target_id == member.org_id
    assert entry.details == {
        "enabled": {"from": False, "to": True},
        "data_location": {"from": "external", "to": "eu"},
    }
    # Everyone's `mcp.use` changed: every active person's client reloads it.
    told = await session.scalars(
        select(EventOutbox.subject_id).where(EventOutbox.type == "access.changed")
    )
    assert member.id in set(told)


async def test_the_settings_name_the_version_they_change(owner: AsyncClient) -> None:
    await mcp_on(owner)
    stale = {"enabled": False, "data_location": "external", "version": 1}
    r = await owner.put("/api/ai/mcp", json=stale)
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "mcp.settings_version_conflict"
    assert r.json()["error"]["details"] == {"current_version": 2}
    bad = {"enabled": True, "data_location": "mars", "version": 2}
    assert (await owner.put("/api/ai/mcp", json=bad)).status_code == 422


async def test_the_admin_sees_every_token_without_its_secret(
    session: AsyncSession, owner: AsyncClient, member_client: AsyncClient, member: User
) -> None:
    await mcp_on(owner)
    mine = await new_token(owner, name="Admin-Laptop")
    theirs = await new_token(member_client, name="Max' Codex", mode="write")
    first = (await owner.get("/api/ai/mcp/tokens", params={"limit": 1})).json()
    rest = (await owner.get("/api/ai/mcp/tokens", params={"cursor": first["next_cursor"]})).json()
    listed = first["items"] + rest["items"]
    assert [t["id"] for t in listed] == [theirs["id"], mine["id"]]
    assert listed[0]["user"] == {"id": str(member.id), "name": member.name}
    assert listed[0]["mode"] == "write" and listed[0]["kind"] == "personal"
    row = await session.get(AccessToken, uuid.UUID(theirs["id"]))
    assert row is not None
    for secret in (mine["secret"], theirs["secret"], row.token_hash.hex()):
        assert secret not in str(first) + str(rest)
    assert "secret" not in listed[0] and "token_hash" not in listed[0]


async def test_the_admin_revokes_any_token(
    session: AsyncSession, owner: AsyncClient, member_client: AsyncClient, owner_user: User
) -> None:
    await mcp_on(owner)
    theirs = await new_token(member_client)
    assert (await owner.delete(f"/api/ai/mcp/tokens/{theirs['id']}")).status_code == 204
    (entry,) = await session.scalars(
        select(AuditLog).where(
            AuditLog.action == "access_token.revoked",
            AuditLog.target_id == uuid.UUID(theirs["id"]),
        )
    )
    assert entry.actor_id == owner_user.id
    shown = (await member_client.get("/api/tokens")).json()["items"][0]
    assert shown["revoked_at"] is not None
    # Even with the switch off, the admin still sees and revokes.
    await mcp_on(owner, enabled=False)
    assert (await owner.get("/api/ai/mcp/tokens")).json()["items"][0]["id"] == theirs["id"]


async def test_only_ai_admins_reach_it(member_client: AsyncClient) -> None:
    for r in (
        await member_client.get("/api/ai/mcp"),
        await member_client.put(
            "/api/ai/mcp", json={"enabled": True, "data_location": "eu", "version": 1}
        ),
        await member_client.get("/api/ai/mcp/tokens"),
        await member_client.delete(f"/api/ai/mcp/tokens/{uuid.uuid4()}"),
    ):
        assert r.status_code == 404 and r.json()["error"]["code"] == "ai.not_found"


async def test_another_organisations_token_is_not_there(
    session: AsyncSession, owner: AsyncClient, make_user: MakeUser
) -> None:
    await mcp_on(owner)
    elsewhere = Organization(name="Andere")
    session.add(elsewhere)
    await session.flush()
    stranger = await make_user(organization=elsewhere)
    foreign = AccessToken(
        org_id=elsewhere.id,
        kind=TokenKind.PERSONAL,
        user_id=stranger.id,
        name="fremd",
        token_hash=b"\x01" * 32,
        mode=TokenMode.READ,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    session.add(foreign)
    await session.flush()
    assert (await owner.get("/api/ai/mcp/tokens")).json()["items"] == []
    r = await owner.delete(f"/api/ai/mcp/tokens/{foreign.id}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "token.not_found"
