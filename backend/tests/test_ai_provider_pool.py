"""A slow provider holds no database connection: checking a connection and listing its
models wait for the provider with no transaction open (pool of one connection)."""

import asyncio
import time
from collections.abc import AsyncIterator

import pytest

from app.core.config import get_settings
from app.core.db import Database, set_database
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub

FAST_ENOUGH = 1.0


@pytest.fixture
async def one_connection(real_db: RealDb) -> AsyncIterator[Database]:
    database = Database(
        get_settings().test_database_url, pool_size=1, max_overflow=0, pool_timeout=10
    )
    set_database(database)
    try:
        yield database
    finally:
        set_database(real_db.database)
        await database.dispose()


async def test_waiting_for_a_provider_holds_no_connection(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    one_connection: Database,
    openai_stub: OpenAIStub,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    made = await owner.post(
        "/api/ai/connections",
        json={"name": "L", "kind": "local", "base_url": openai_stub.base_url, "models": ["m"]},
    )
    connection_id = made.json()["id"]
    openai_stub.state.delay = 1.5
    checking = asyncio.create_task(owner.post(f"/api/ai/connections/{connection_id}/test", json={}))
    listing = asyncio.create_task(
        owner.post(f"/api/ai/connections/{connection_id}/models", json={"version": 1})
    )
    try:
        while len(openai_stub.state.log) < 2:  # noqa: ASYNC110 (another thread fills it)
            await asyncio.sleep(0.02)
        started = time.perf_counter()
        me = await owner.get("/api/auth/me")
        assert me.status_code == 200 and time.perf_counter() - started < FAST_ENOUGH
    finally:
        checked, listed = await asyncio.gather(checking, listing)
    assert checked.json()["status"] == "ok"
    assert listed.status_code == 200 and listed.json()["version"] == 2
