"""Async engine, session factory and the request-scoped session dependency."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)

AfterCommit = Callable[[AsyncSession], Awaitable[None]]
_AFTER_COMMIT = "herd.after_commit"


def make_engine(url: str | URL | None = None, **kwargs: Any) -> AsyncEngine:
    """hide_parameters: a failing statement's error carries no bound values (request
    data, password hashes, token hashes), so nothing that logs it can leak them."""
    return create_async_engine(
        url or get_settings().database(), pool_pre_ping=True, hide_parameters=True, **kwargs
    )


class Database:
    """Holds the engine and session factory for one application instance."""

    def __init__(self, url: str | URL | None = None, **engine_kwargs: Any) -> None:
        self.engine = make_engine(url, **engine_kwargs)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def dispose(self) -> None:
        await self.engine.dispose()


_database: Database | None = None


def get_database() -> Database:
    global _database
    if _database is None:
        _database = Database()
    return _database


def set_database(database: Database | None) -> None:
    global _database
    _database = database


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, committed on success, before the
    response is sent (`SessionDep` declares it with scope="function"); a failed commit
    becomes the request's error response."""
    async with get_database().session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            discard_after_commit(session)
            await session.rollback()
            raise
        await run_after_commit(session)


def after_commit(session: AsyncSession, action: AfterCommit) -> None:
    """Run `action` once the request's transaction has committed, in a transaction of
    its own on the same session (for work that must not happen if the commit fails,
    such as removing files whose rows were deleted). Dropped when the request fails."""
    session.info.setdefault(_AFTER_COMMIT, []).append(action)


def discard_after_commit(session: AsyncSession) -> None:
    session.info.pop(_AFTER_COMMIT, None)


def after_commit_mark(session: AsyncSession) -> int:
    """How many actions are registered: a mark to go back to when a savepoint is rolled
    back (`discard_after_commit_since`)."""
    return len(session.info.get(_AFTER_COMMIT, []))


def discard_after_commit_since(session: AsyncSession, mark: int) -> None:
    """Drop the actions registered after `mark` (their savepoint was rolled back)."""
    actions: list[AfterCommit] = session.info.get(_AFTER_COMMIT, [])
    del actions[mark:]


async def run_after_commit(session: AsyncSession) -> None:
    """The registered actions, each in its own transaction (a savepoint when the
    session is still inside one, as in tests); a failing action is logged and rolled
    back, never raised: the request's own work is already committed."""
    actions: list[AfterCommit] = session.info.pop(_AFTER_COMMIT, [])
    for action in actions:
        try:
            if session.in_transaction():
                async with session.begin_nested():
                    await action(session)
            else:
                async with session.begin():
                    await action(session)
        except Exception as exc:
            logger.warning("after-commit action failed", extra={"error": type(exc).__name__})
