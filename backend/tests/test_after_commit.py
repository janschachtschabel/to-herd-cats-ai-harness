"""`core.db.after_commit`: actions that run once the transaction has committed."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import after_commit, discard_after_commit, run_after_commit


async def test_actions_run_in_order_and_a_failure_does_not_stop_the_rest(
    session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    ran: list[str] = []

    async def first(s: AsyncSession) -> None:
        assert await s.scalar(text("SELECT 1")) == 1
        ran.append("first")

    async def broken(s: AsyncSession) -> None:
        raise RuntimeError("secret detail")

    async def last(s: AsyncSession) -> None:
        ran.append("last")

    for action in (first, broken, last):
        after_commit(session, action)
    await run_after_commit(session)
    assert ran == ["first", "last"]
    assert any(r.getMessage() == "after-commit action failed" for r in caplog.records)
    assert "secret detail" not in caplog.text
    await run_after_commit(session)  # each action runs once
    assert ran == ["first", "last"]


async def test_discarded_actions_never_run(session: AsyncSession) -> None:
    ran: list[str] = []

    async def action(s: AsyncSession) -> None:
        ran.append("x")

    after_commit(session, action)
    discard_after_commit(session)
    await run_after_commit(session)
    assert ran == []
