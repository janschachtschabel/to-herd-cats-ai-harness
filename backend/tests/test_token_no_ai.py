"""Plan M8 task 4, carry-in: an external client is an AI reading the organisation's data,
so `mcp.use` needs a person who is not expressly kept from AI. The organisation's one
such mechanism is a person's own AI assignment with `no_ai` (spec 7.2): it takes
`mcp.use` away, at once for tokens already made. Having no model at all (no
assignment applies) is not an exclusion: `mcp.use` does not depend on a model."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Unauthorized
from app.modules.users.models import User
from tests.factories_tokens import bearer, mcp_on, new_token, resolver

USERS = "/api/ai/assignments/users"


async def _no_ai(owner: AsyncClient, user: User) -> dict[str, Any]:
    r = await owner.put(f"{USERS}/{user.id}", json={"no_ai": True, "version": None})
    assert r.status_code == 200, r.text
    made: dict[str, Any] = r.json()
    return made


async def _permissions(client: AsyncClient) -> list[str]:
    permissions: list[str] = (await client.get("/api/auth/me")).json()["permissions"]
    return permissions


async def test_without_any_model_a_person_still_holds_mcp_use(
    session: AsyncSession, owner: AsyncClient, member_client: AsyncClient
) -> None:
    await mcp_on(owner)
    assert "ai.use" not in await _permissions(member_client)
    assert "mcp.use" in await _permissions(member_client)
    token = await new_token(member_client)
    assert (await resolver(session).resolve(bearer(token))).token_id is not None


async def test_a_person_kept_from_ai_loses_mcp_use_and_their_tokens_stop(
    session: AsyncSession, owner: AsyncClient, member_client: AsyncClient, member: User
) -> None:
    await mcp_on(owner)
    token = await new_token(member_client)
    assignment = await _no_ai(owner, member)
    assert "mcp.use" not in await _permissions(member_client)
    r = await member_client.get("/api/tokens")
    assert r.status_code == 404 and r.json()["error"]["code"] == "token.not_found"
    with pytest.raises(Unauthorized):
        await resolver(session).resolve(bearer(token))
    r = await owner.delete(f"{USERS}/{member.id}", params={"version": assignment["version"]})
    assert r.status_code == 204, r.text
    assert "mcp.use" in await _permissions(member_client)
    assert (await resolver(session).resolve(bearer(token))).token_id is not None
