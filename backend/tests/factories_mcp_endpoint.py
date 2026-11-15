"""The `/mcp` endpoint under test (plan M8 task 2): `mcp_app` is a public app on the
test session; `connect(secret)` opens a real client of the MCP SDK against it (over
ASGI, the bearer token in its header), `mcp_http` an HTTP client for what the SDK would
not send (no token, an `Origin`)."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.web.public import create_public_app
from tests.app_session import session_override

BASE = "http://test"
URL = f"{BASE}/mcp"
JSON_ACCEPT = {"Accept": "application/json, text/event-stream"}

Connect = Callable[..., AbstractAsyncContextManager[Client]]


@pytest.fixture
def mcp_app(session: AsyncSession) -> FastAPI:
    app = create_public_app()
    app.dependency_overrides[get_session] = session_override(session)
    return app


def http_client(app: FastAPI, headers: dict[str, str] | None = None) -> httpx2.AsyncClient:
    transport = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(transport=transport, base_url=BASE, headers=headers or {})


@pytest.fixture
def connect(mcp_app: FastAPI) -> Connect:
    @asynccontextmanager
    async def _connect(secret: str, *, mode: str = "legacy") -> AsyncIterator[Client]:
        http = http_client(mcp_app, {"Authorization": f"Bearer {secret}"})
        async with http:
            transport = streamable_http_client(URL, http_client=http)
            async with Client(transport, mode=mode, cache=None) as client:  # type: ignore[arg-type]
                yield client

    return _connect


@pytest.fixture
async def mcp_http(mcp_app: FastAPI) -> AsyncIterator[httpx2.AsyncClient]:
    async with http_client(mcp_app, JSON_ACCEPT) as client:
        yield client


def text_of(result: CallToolResult) -> str:
    return "\n".join(b.text for b in result.content if isinstance(b, TextContent))


def rpc(method: str, params: dict[str, Any] | None = None, id_: int = 1) -> dict[str, Any]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        body["params"] = params
    return body


INITIALIZE = rpc(
    "initialize",
    {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "probe", "version": "1"},
    },
)
