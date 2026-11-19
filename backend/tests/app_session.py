"""`get_session` for apps under test, on the test session (public and internal)."""

from collections.abc import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import (
    discard_after_commit,
    discard_after_rollback,
    run_after_commit,
    run_after_rollback,
)


def session_override(session: AsyncSession) -> Callable[[], AsyncIterator[AsyncSession]]:
    """`get_session` for apps under test, on the test session.

    Mirrors app.core.db.get_session: each request is its own unit of work and a failed
    request rolls back only its own changes (a savepoint per request)."""

    async def _session_override() -> AsyncIterator[AsyncSession]:
        nested = await session.begin_nested()
        try:
            yield session
            await session.flush()
            if nested.is_active:
                await nested.commit()
        except Exception:
            discard_after_commit(session)
            if nested.is_active:
                await nested.rollback()
            await run_after_rollback(session)
            raise
        discard_after_rollback(session)
        await run_after_commit(session)

    return _session_override
