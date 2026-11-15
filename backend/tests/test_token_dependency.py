"""Plan M8 task 1: `TokenActorDep`, the dependency `/mcp` mounts (task 2), on a probe
route: the token's actor for a good bearer header, 401 `token.invalid` in the error
shape otherwise, agent tokens included (they act only from task 4 on)."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import install_error_handlers
from app.modules.tokens.models import AccessToken, TokenKind, TokenMode
from app.modules.tokens.resolve import TokenActorDep
from app.modules.tokens.values import token_digest
from app.modules.users.models import User
from tests.app_session import session_override
from tests.factories_tokens import bearer, mcp_on, new_token


@pytest.fixture
async def probe(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/probe")
    async def _probe(found: TokenActorDep) -> dict[str, Any]:
        return {"user": str(found.actor.principal.id), "mode": found.mode, "name": found.name}

    app.dependency_overrides[get_session] = session_override(session)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_the_dependency_gives_the_tokens_actor(
    probe: AsyncClient, owner: AsyncClient, member_client: AsyncClient, member: User
) -> None:
    await mcp_on(owner)
    token = await new_token(member_client, mode="write", name="Codex")
    r = await probe.get("/probe", headers={"Authorization": bearer(token)})
    assert r.status_code == 200, r.text
    assert r.json() == {"user": str(member.id), "mode": "write", "name": "Codex"}
    lower = await probe.get("/probe", headers={"Authorization": "bearer " + token["secret"]})
    assert lower.status_code == 200  # the scheme's case does not matter


async def test_anything_else_is_401_in_the_error_shape(
    session: AsyncSession, probe: AsyncClient, owner: AsyncClient, member: User
) -> None:
    await mcp_on(owner)
    secret = "herd_agt_" + "B" * 43
    session.add(
        AccessToken(
            org_id=member.org_id,
            kind=TokenKind.AGENT,
            user_id=member.id,
            name="extern",
            token_hash=token_digest(secret),
            mode=TokenMode.READ,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    await session.flush()
    for headers in ({}, {"Authorization": bearer(secret)}, {"Authorization": str(uuid.uuid4())}):
        r = await probe.get("/probe", headers=headers)
        assert r.status_code == 401, r.text
        error = r.json()["error"]
        assert error["code"] == "token.invalid" and len(error["trace_id"]) == 32
