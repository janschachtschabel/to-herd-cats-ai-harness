"""Test fixtures: real Postgres (herd_test), one rolled-back transaction per test."""

import json
import os
from collections.abc import AsyncIterator
from typing import Any

os.environ["HERD_ENVIRONMENT"] = "test"  # before any app import: enables /api/_test/*

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.core.migrations import stamp_head  # noqa: E402
from app.core.models_base import Base  # noqa: E402
from app.web.internal import create_internal_app, get_engine  # noqa: E402
from app.web.public import create_public_app  # noqa: E402

configure_logging(get_settings())


def json_lines(text: str) -> list[dict[str, Any]]:
    """The JSON log lines in captured output; anything else (pytest noise) is skipped."""
    lines = []
    for raw in text.splitlines():
        try:
            parsed = json.loads(raw)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            lines.append(parsed)
    return lines


def last_line(capsys: pytest.CaptureFixture[str], message: str) -> str:
    """The last captured JSON log line whose message is `message`, as raw text."""
    matches = [
        line for line in json_lines(capsys.readouterr().out) if line.get("message") == message
    ]
    assert matches, f"no log line with message {message!r}"
    return json.dumps(matches[-1])


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(get_settings().test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(stamp_head)  # the schema above is what head describes
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_public_app()

    async def _session_override() -> AsyncIterator[AsyncSession]:
        # Mirrors app.core.db.get_session: each request is its own unit of work and a
        # failed request rolls back only its own changes (a savepoint per request).
        nested = await session.begin_nested()
        try:
            yield session
            await session.flush()
            if nested.is_active:
                await nested.commit()
        except Exception:
            if nested.is_active:
                await nested.rollback()
            raise

    app.dependency_overrides[get_session] = _session_override
    # raise_app_exceptions=False: let the 500 handler's response reach the test.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def internal_client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """The internal app (probes, metrics), reading the test database."""
    app = create_internal_app()
    app.dependency_overrides[get_engine] = lambda: engine
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://internal") as client:
        yield client
