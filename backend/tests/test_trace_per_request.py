"""A trace id names one request (rule 7), also on a keep-alive connection after a
large upload (review M2 R11). Runs the real app on a real port (uvicorn): the leak
lived in the server's flow control, which an in-process transport never uses."""

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
import uvicorn

from app.web.public import create_public_app
from tests.factories import login
from tests.real_db import RealDb


@pytest.fixture
async def base_url(real_db: RealDb) -> AsyncIterator[str]:
    config = uvicorn.Config(
        create_public_app(), host="127.0.0.1", port=0, log_config=None, lifespan="off"
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110 -- uvicorn offers no event for it
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    await task


async def _trace_ids(client: httpx.AsyncClient, count: int) -> list[str]:
    ids = []
    for _ in range(count):
        r = await client.get("/api/pages/01a1d2d9-2de5-75db-9dc6-a6fa1307273d")
        assert r.status_code == 404
        ids.append(r.json()["error"]["trace_id"])
    return ids


async def test_a_trace_id_is_never_reused_on_one_connection(
    base_url: str, real_db: RealDb
) -> None:
    limits = httpx.Limits(max_connections=1)  # every request on the same connection
    headers = {"X-Requested-With": "herd"}
    async with httpx.AsyncClient(base_url=base_url, limits=limits, headers=headers) as client:
        await login(client, real_db.owner_email)
        space = (await client.post("/api/spaces", json={"name": "T", "kind": "team"})).json()
        page = (await client.post(f"/api/spaces/{space['id']}/pages", json={"title": "S"})).json()
        before = await _trace_ids(client, 3)
        r = await client.post(
            f"/api/pages/{page['id']}/attachments",
            params={"filename": "gross.txt"},
            content=b"x" * (2 * 1024 * 1024),
        )
        assert r.status_code == 201, r.text
        after = await _trace_ids(client, 3)
    assert len(set(before + after)) == 6, (before, after)
