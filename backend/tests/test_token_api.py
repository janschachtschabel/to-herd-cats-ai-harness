"""Plan M8 task 1: one's own access tokens over the session API (`/api/tokens`). The
clear text is shown once, at creation, and stored nowhere (only its SHA-256); lists
never carry it or the hash. Without `mcp.use` (the organisation's switch off, or a
guest) there is nothing to see: 404 `token.not_found`, like an unknown id."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import SpaceRole
from app.modules.audit.models import AuditLog
from app.modules.spaces.models import SpaceKind
from app.modules.tokens.models import AccessToken
from app.modules.users.models import User
from tests.factories_spaces import MakeSpace
from tests.factories_tokens import mcp_on, new_token

SHOWN = {
    "id",
    "kind",
    "agent_id",
    "name",
    "mode",
    "space_ids",
    "expires_at",
    "last_used_at",
    "revoked_at",
    "created_at",
}


async def test_the_clear_text_is_shown_once_and_only_its_hash_is_kept(
    session: AsyncSession, owner: AsyncClient, member_client: AsyncClient, member: User
) -> None:
    await mcp_on(owner)
    made = await new_token(member_client, name="Claude Code", expires_in_days=90)
    secret = made.pop("secret")
    assert set(made) == SHOWN
    assert secret.startswith("herd_pat_") and len(secret) >= len("herd_pat_") + 43
    assert made["kind"] == "personal" and made["mode"] == "read" and made["space_ids"] is None
    expires = datetime.fromisoformat(made["expires_at"])
    assert abs(expires - (datetime.now(UTC) + timedelta(days=90))) < timedelta(minutes=1)
    row = await session.get(AccessToken, uuid.UUID(made["id"]))
    assert row is not None and row.user_id == member.id and row.org_id == member.org_id
    assert row.token_hash == hashlib.sha256(secret.encode()).digest()
    stored = " ".join(str(getattr(row, c.key)) for c in AccessToken.__table__.columns)
    assert secret not in stored and secret[len("herd_pat_") :] not in stored
    listed = (await member_client.get("/api/tokens")).json()
    assert [set(t) for t in listed["items"]] == [SHOWN]
    assert secret not in str(listed) and row.token_hash.hex() not in str(listed)
    again = await new_token(member_client)
    assert again["secret"] != secret  # random, never derived from anything


async def test_own_tokens_are_listed_newest_first_page_by_page(
    owner: AsyncClient, member_client: AsyncClient, owner_user: User
) -> None:
    await mcp_on(owner)
    names = [f"t{i}" for i in range(3)]
    for name in names:
        await new_token(member_client, name=name)
    await new_token(owner, name="fremd")  # not the member's
    first = (await member_client.get("/api/tokens", params={"limit": 2})).json()
    assert [t["name"] for t in first["items"]] == ["t2", "t1"]
    rest = await member_client.get("/api/tokens", params={"cursor": first["next_cursor"]})
    assert [t["name"] for t in rest.json()["items"]] == ["t0"]
    assert rest.json()["next_cursor"] is None


async def test_a_scope_names_spaces_the_person_reads(
    owner: AsyncClient, member_client: AsyncClient, member: User, make_space: MakeSpace
) -> None:
    await mcp_on(owner)
    mine = await make_space(SpaceKind.TEAM, members=[(member, SpaceRole.VIEWER)])
    hidden = await make_space(SpaceKind.TEAM)
    made = await new_token(member_client, space_ids=[str(mine.id), str(mine.id)])
    assert made["space_ids"] == [str(mine.id)]
    for space_ids in ([str(hidden.id)], [str(uuid.uuid4())], []):
        r = await member_client.post(
            "/api/tokens",
            json={"name": "x", "mode": "read", "expires_in_days": 1, "space_ids": space_ids},
        )
        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] in {"token.space_invalid", "validation_failed"}


async def test_expiry_is_required_and_at_most_a_year(
    owner: AsyncClient, member_client: AsyncClient
) -> None:
    await mcp_on(owner)
    for days in (0, 366, None):
        body = {"name": "x", "mode": "read", "expires_in_days": days}
        r = await member_client.post("/api/tokens", json=body)
        assert r.status_code == 422, r.text
    r = await member_client.post("/api/tokens", json={"name": "x", "mode": "admin"})
    assert r.status_code == 422


async def test_revoking_ones_own_token(
    session: AsyncSession, owner: AsyncClient, member_client: AsyncClient
) -> None:
    await mcp_on(owner)
    made = await new_token(member_client)
    assert (await member_client.delete(f"/api/tokens/{made['id']}")).status_code == 204
    assert (await member_client.delete(f"/api/tokens/{made['id']}")).status_code == 204
    listed = (await member_client.get("/api/tokens")).json()["items"]
    assert listed[0]["revoked_at"] is not None
    entries = await session.scalars(
        select(AuditLog.action).where(AuditLog.target_id == uuid.UUID(made["id"]))
    )
    assert sorted(entries) == ["access_token.created", "access_token.revoked"]  # once


async def test_someone_elses_token_answers_like_an_unknown_one(
    owner: AsyncClient, member_client: AsyncClient
) -> None:
    await mcp_on(owner)
    owners = await new_token(owner)
    for token_id in (owners["id"], str(uuid.uuid4())):
        r = await member_client.delete(f"/api/tokens/{token_id}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "token.not_found"
    assert (await owner.get("/api/tokens")).json()["items"][0]["revoked_at"] is None


async def test_without_mcp_use_there_is_nothing_to_see(
    owner: AsyncClient, member_client: AsyncClient, guest_client: AsyncClient
) -> None:
    made = None
    for switched_on in (False, True):
        if switched_on:
            await mcp_on(owner)
            made = await new_token(member_client)
        clients = [guest_client] if switched_on else [member_client, owner]
        for client in clients:
            for r in (
                await client.get("/api/tokens"),
                await client.post(
                    "/api/tokens", json={"name": "x", "mode": "read", "expires_in_days": 1}
                ),
                await client.delete(f"/api/tokens/{uuid.uuid4()}"),
            ):
                assert r.status_code == 404, r.text
                assert r.json()["error"]["code"] == "token.not_found"
            me = (await client.get("/api/auth/me")).json()
            assert "mcp.use" not in me["permissions"]
    assert made is not None
    await mcp_on(owner, enabled=False)
    r = await member_client.delete(f"/api/tokens/{made['id']}")
    assert r.status_code == 404  # off: not even one's own
