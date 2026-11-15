"""Plan M8 task 1 (decision 6): each token's calls are limited per minute in Postgres
(`HERD_MCP_RATE_PER_MINUTE`), so the limit holds across API nodes: two databases'
worth of connections (two "nodes") share one count."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.db import Database
from app.core.errors import RateLimited
from app.modules.tokens.models import AccessToken, McpSetting, TokenKind, TokenMode
from app.modules.tokens.resolve import TokenResolver
from app.modules.tokens.values import new_secret, token_digest
from app.modules.users.models import User
from tests.real_db import RealDb
from tests.support.clock import SettableClock

LIMIT = 5


async def _token(real_db: RealDb) -> str:
    secret = new_secret(TokenKind.PERSONAL)
    async with real_db.database.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == real_db.member_email))
        assert user is not None
        session.add(McpSetting(org_id=user.org_id, enabled=True))
        session.add(
            AccessToken(
                org_id=user.org_id,
                kind=TokenKind.PERSONAL,
                user_id=user.id,
                name="Knoten",
                token_hash=token_digest(secret),
                mode=TokenMode.READ,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        await session.commit()
    return secret


async def test_the_limit_holds_across_two_nodes(real_db: RealDb) -> None:
    secret = await _token(real_db)
    settings = get_settings().model_copy(update={"mcp_rate_per_minute": LIMIT})
    clock = SettableClock(datetime.now(UTC))
    nodes = [Database(get_settings().test_database_url) for _ in range(2)]

    async def call(node: Database) -> str:
        async with node.session_factory() as session:
            try:
                await TokenResolver(session, settings, clock).resolve(f"Bearer {secret}")
            except RateLimited as refused:
                assert refused.retry_after is not None
                return refused.code
            await session.commit()
            return "ok"

    try:
        answers = await asyncio.gather(*(call(nodes[i % 2]) for i in range(LIMIT * 2 + 2)))
    finally:
        for node in nodes:
            await node.dispose()
    assert answers.count("ok") == LIMIT
    assert set(answers) == {"ok", "mcp.rate_limited"}


@pytest.mark.parametrize("limit", [0, 10_001])
def test_the_setting_has_bounds(limit: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERD_MCP_RATE_PER_MINUTE", str(limit))
    with pytest.raises(ValidationError):
        Settings()


def test_the_default_is_120_a_minute() -> None:
    assert get_settings().mcp_rate_per_minute == 120
