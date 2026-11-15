"""MCP server fixtures: `mcp_stub` (a real Streamable HTTP MCP server on 127.0.0.1,
https for `mcp.test`, reset per test) and `mcp_egress` (the egress guard resolving
`*.test` to 127.0.0.1, trusting the stub's certificate and allowing 127.0.0.1 in
addition; production rules stay as they are), plus helpers to set up a server
through the API."""

import ipaddress
import ssl
from collections.abc import Iterator
from typing import Any

import pytest
from httpx import AsyncClient

from app.core import egress
from app.core.egress import Network
from tests.support.mcp_stub import McpStub

SERVERS = "/api/ai/mcp-servers"


@pytest.fixture(scope="session")
def _mcp_stub() -> Iterator[McpStub]:
    stub = McpStub().start()
    yield stub
    stub.stop()


@pytest.fixture
def mcp_stub(_mcp_stub: McpStub) -> Iterator[McpStub]:
    _mcp_stub.state.reset()
    yield _mcp_stub
    _mcp_stub.state.reset()


async def resolve_test_names(host: str, port: int) -> list[str]:
    if host.endswith(".test"):
        return ["127.0.0.1"]
    raise OSError("unknown name")


def mcp_network(stub: McpStub, resolver: Any = resolve_test_names) -> Network:
    return Network(
        resolver=resolver,
        ssl_context=ssl.create_default_context(cafile=str(stub.cert_path)),
        extra_allowed=(ipaddress.ip_network("127.0.0.1/32"),),
    )


@pytest.fixture
def mcp_egress(mcp_stub: McpStub, monkeypatch: pytest.MonkeyPatch) -> McpStub:
    monkeypatch.setattr(egress, "_network", mcp_network(mcp_stub))
    return mcp_stub


async def make_server(admin: AsyncClient, stub: McpStub, **fields: Any) -> dict[str, Any]:
    body = {"name": "Tracker", "url": stub.url, **fields}
    response = await admin.post(SERVERS, json=body)
    assert response.status_code == 201, response.text
    made: dict[str, Any] = response.json()
    return made


async def tools_of(admin: AsyncClient, server_id: object) -> dict[str, dict[str, Any]]:
    response = await admin.get(f"{SERVERS}/{server_id}/tools", params={"limit": 100})
    assert response.status_code == 200, response.text
    return {t["name"]: t for t in response.json()["items"]}


async def approve(admin: AsyncClient, server_id: object, tool: dict[str, Any]) -> dict[str, Any]:
    response = await admin.post(
        f"{SERVERS}/{server_id}/tools/{tool['id']}/approve", json={"version": tool["version"]}
    )
    assert response.status_code == 200, response.text
    approved: dict[str, Any] = response.json()
    return approved


async def classify(
    admin: AsyncClient, server_id: object, tool: dict[str, Any], classification: str
) -> dict[str, Any]:
    """The admin's class for a tool (a new one is proposed `write` unless its server
    annotates it read-only and the catalogue suggests `read`; module review M8 1,
    finding 7). Loosening a tool the server does not annotate read-only is confirmed."""
    body = {"classification": classification, "version": tool["version"], "confirm_loosen": True}
    response = await admin.patch(f"{SERVERS}/{server_id}/tools/{tool['id']}", json=body)
    assert response.status_code == 200, response.text
    classified: dict[str, Any] = response.json()
    return classified


async def approve_as_listed(admin: AsyncClient, server_id: object) -> None:
    """Approve every tool of the server, those it annotates read-only as `read`."""
    for tool in (await tools_of(admin, server_id)).values():
        if tool["read_only_hint"] and tool["classification"] != "read":
            tool = await classify(admin, server_id, tool, "read")
        await approve(admin, server_id, tool)
