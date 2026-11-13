"""The production transaction boundary in tests: the real `get_session`, real commits.

Most tests run inside one rolled-back transaction (conftest). Tests that need what
production does (commit timing, concurrent requests over separate connections, the
advisory locks) use these fixtures instead: the app's own `Database` points at
`herd_test`, nothing is overridden, and every table is emptied afterwards.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.types import ASGIApp

from app.core.config import get_settings
from app.core.db import Database, set_database
from app.core.principal import SystemRole
from app.modules.orgs.models import Organization
from app.modules.spaces.service import SpaceService
from app.modules.users.models import User
from app.web.public import create_public_app
from tests.factories import _PASSWORD_HASH


@dataclass
class RealDb:
    database: Database
    org_id: object
    owner_email: str
    member_email: str


async def _truncate_all(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        names = (
            await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
                    " AND tablename <> 'alembic_version'"
                )
            )
        ).scalars()
        tables = ", ".join(f'"{name}"' for name in names)
        if tables:
            await conn.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
async def real_db(engine: AsyncEngine) -> AsyncIterator[RealDb]:
    """An org with an owner and a member (each with a personal space), committed."""
    database = Database(get_settings().test_database_url)
    set_database(database)
    try:
        async with database.session_factory() as session:
            org = Organization(name="Real Org", slug="real-org")
            session.add(org)
            await session.flush()
            emails = {}
            for role in (SystemRole.OWNER, SystemRole.MEMBER):
                user = User(
                    org_id=org.id,
                    email=f"{role}@real.example.com",
                    name=f"Real {role}",
                    password_hash=_PASSWORD_HASH,
                    system_role=role,
                )
                session.add(user)
                await session.flush()
                await SpaceService(session).create_personal(user)
                emails[role] = user.email
            await session.commit()
        yield RealDb(database, org.id, emails[SystemRole.OWNER], emails[SystemRole.MEMBER])
    finally:
        set_database(None)
        await _truncate_all(database.engine)
        await database.dispose()


MakeRealClient = Callable[..., Awaitable[AsyncClient]]


@pytest.fixture
def real_app(real_db: RealDb) -> FastAPI:
    """The public app on the real session dependency (a test may override settings)."""
    return create_public_app()


@pytest.fixture
async def make_real_client(real_app: FastAPI) -> AsyncIterator[MakeRealClient]:
    """Clients of `real_app`; `csrf=True` adds the header, `client_ip` is the peer
    address, `wrap` puts an ASGI wrapper around the app."""
    app = real_app
    clients: list[AsyncClient] = []

    async def _make(
        *,
        csrf: bool = True,
        client_ip: str = "127.0.0.1",
        wrap: Callable[[ASGIApp], ASGIApp] | None = None,
    ) -> AsyncClient:
        headers = {"X-Requested-With": "herd"} if csrf else {}
        client = AsyncClient(
            transport=ASGITransport(
                app=wrap(app) if wrap else app,
                raise_app_exceptions=False,
                client=(client_ip, 12345),
            ),
            base_url="http://test",
            headers=headers,
        )
        clients.append(client)
        return client

    yield _make
    for client in clients:
        await client.aclose()
