"""Async engine, session factory and the request-scoped session dependency."""

from collections.abc import AsyncIterator

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def make_engine(url: str | URL | None = None) -> AsyncEngine:
    return create_async_engine(url or get_settings().database(), pool_pre_ping=True)


class Database:
    """Holds the engine and session factory for one application instance."""

    def __init__(self, url: str | URL | None = None) -> None:
        self.engine = make_engine(url)
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
    """FastAPI dependency: one session per request, committed on success."""
    async with get_database().session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
