"""Retention of `/mcp`'s call rows (module review M8 1, finding 14): the due loop's
cleanup removes `mcp_call` rows older than MCP_CALL_RETENTION, in bounded batches,
with the automations' log. Real commits (the due loop's own sessions)."""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.modules.mcp_tools.models import McpCall, Outcome
from app.modules.tokens.models import AccessToken, TokenKind, TokenMode
from app.modules.tokens.values import token_digest
from app.modules.users.models import User
from app.worker.due import MCP_CALL_RETENTION, DueLoop
from tests.real_db import RealDb
from tests.support.clock import SettableClock

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


async def test_old_call_rows_go_in_batches(real_db: RealDb) -> None:
    async with real_db.database.session_factory() as session:
        owner = await session.scalar(select(User).where(User.email == real_db.owner_email))
        assert owner is not None
        token = AccessToken(
            org_id=owner.org_id,
            kind=TokenKind.PERSONAL,
            user_id=owner.id,
            name="Codex",
            token_hash=token_digest("herd_pat_" + secrets.token_urlsafe(32)),
            mode=TokenMode.READ,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        session.add(token)
        await session.flush()
        old = NOW - MCP_CALL_RETENTION - timedelta(minutes=1)
        young = NOW - MCP_CALL_RETENTION + timedelta(minutes=1)
        session.add_all(
            McpCall(
                org_id=owner.org_id,
                token_id=token.id,
                tool="search_pages",
                outcome=Outcome.OK,
                duration_ms=3,
                created_at=at,
            )
            for at in [old] * 3 + [young]
        )
        await session.commit()
    loop = DueLoop(real_db.database, clock=SettableClock(NOW), cleanup_batch=2)
    assert await loop.cleanup() == (0, 0, 3)
    async with real_db.database.session_factory() as session:
        left = await session.scalar(select(func.count()).select_from(McpCall))
    assert left == 1
