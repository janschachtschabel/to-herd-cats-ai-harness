"""Test fixtures: real Postgres (herd_test), one rolled-back transaction per test."""

import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

os.environ["HERD_ENVIRONMENT"] = "test"  # before any app import: enables /api/_test/*

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import MetaData  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import (  # noqa: E402
    discard_after_commit,
    get_session,
    make_engine,
    run_after_commit,
)
from app.core.logging import configure_logging  # noqa: E402
from app.core.migrations import upgrade_head  # noqa: E402
from app.web.internal import create_internal_app, get_engine  # noqa: E402
from app.web.public import create_public_app  # noqa: E402
from tests.factories import (  # noqa: E402, F401
    guest,
    guest_client,
    make_user,
    member,
    member_client,
    org,
    owner,
    owner_user,
)
from tests.factories_groups import group, group_with_member, make_group  # noqa: E402, F401
from tests.factories_spaces import make_space, open_space, team_space  # noqa: E402, F401
from tests.factories_wiki import wiki  # noqa: E402, F401
from tests.real_db import make_real_client, real_app, real_db  # noqa: E402, F401

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


def _drop_everything(connection: Connection) -> None:
    """Whatever an earlier run left behind, including alembic_version."""
    existing = MetaData()
    existing.reflect(connection)
    existing.drop_all(connection)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Files (attachments) of each test go to a directory of its own."""
    path = tmp_path / "data"
    monkeypatch.setattr(get_settings(), "data_dir", path)
    return path


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    """The schema is built by the migrations, so the tests run against what production
    runs; test_migrations checks that the migrated schema matches the models."""
    engine = make_engine(get_settings().test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(_drop_everything)
        await conn.run_sync(upgrade_head)
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


MakeClient = Callable[..., Awaitable[AsyncClient]]


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
            raise
        await run_after_commit(session)

    return _session_override


@pytest.fixture
async def make_client(session: AsyncSession) -> AsyncIterator[MakeClient]:
    """New clients of one public app, all on the test session; each has its own cookies.

    `csrf=True` sends the `X-Requested-With: herd` header the browser app sends."""
    app = create_public_app()
    _session_override = session_override(session)

    app.dependency_overrides[get_session] = _session_override
    # raise_app_exceptions=False: let the 500 handler's response reach the test.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    clients: list[AsyncClient] = []

    async def _make(*, csrf: bool = False) -> AsyncClient:
        headers = {"X-Requested-With": "herd"} if csrf else {}
        client = AsyncClient(transport=transport, base_url="http://test", headers=headers)
        clients.append(client)
        return client

    yield _make
    for client in clients:
        await client.aclose()


@pytest.fixture
async def client(make_client: MakeClient) -> AsyncClient:
    """An anonymous client without the CSRF header."""
    return await make_client()


@pytest.fixture
async def internal_client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """The internal app (probes, metrics), reading the test database."""
    app = create_internal_app()
    app.dependency_overrides[get_engine] = lambda: engine
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://internal") as client:
        yield client
