"""External tools in a run: `ext` is the agent bench with the MCP stub as server
`Tracker` (no credential) whose two tools are approved: `search_issues` (classified
`read`, the stub annotates it read-only) and `create_issue` (`write`). The agent has
no entry for either yet: `grant` gives them, `level` sets the agent's level."""

import ipaddress
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import egress
from app.modules.agents.run_models import EventKind, Run, RunEvent
from tests.factories_agents import Bench
from tests.factories_mcp import (
    SERVERS,
    approve_as_listed,
    make_server,
    mcp_network,
    tools_of,
)
from tests.support.mcp_stub import McpStub


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


@dataclass
class Ext:
    bench: Bench
    stub: McpStub
    server: dict[str, Any]

    @property
    def admin(self) -> AsyncClient:
        return self.bench.people.admin

    @property
    def agent_url(self) -> str:
        return f"/api/agents/{self.bench.agent.id}"

    async def grants(self) -> dict[str, Any]:
        r = await self.admin.get(f"{self.agent_url}/tools")
        assert r.status_code == 200, r.text
        body: dict[str, Any] = r.json()
        return body

    async def name(self, tool: str) -> str:
        """The run's name of one of the server's tools (`ext_…`), from the grants."""
        for entry in (await self.grants())["tools"]:
            if (entry["external"] or {}).get("tool_name") == tool:
                found: str = entry["name"]
                return found
        raise AssertionError(f"{tool} is not listed")

    async def grant(self, **policies: str) -> None:
        """Entries by the server's tool name (`search_issues="allow"`)."""
        tools = [{"tool": await self.name(t), "policy": p} for t, p in policies.items()]
        version = (await self.grants())["version"]
        r = await self.admin.put(
            f"{self.agent_url}/tools", json={"tools": tools, "version": version}
        )
        assert r.status_code == 200, r.text

    async def level(self, level: int) -> None:
        version = (await self.grants())["version"]
        r = await self.admin.patch(self.agent_url, json={"level": level, "version": version})
        assert r.status_code == 200, r.text

    async def tools(self) -> dict[str, dict[str, Any]]:
        return await tools_of(self.admin, self.server["id"])

    async def patch_server(self, **fields: Any) -> None:
        version = (await self.admin.get(f"{SERVERS}/{self.server['id']}")).json()["version"]
        r = await self.admin.patch(
            f"{SERVERS}/{self.server['id']}", json={**fields, "version": version}
        )
        assert r.status_code == 200, r.text

    def offered(self, request: int = -1) -> dict[str, dict[str, Any]]:
        """The tools the model was offered in a request to it (by name)."""
        body = self.bench.stub.state.log[request].body
        return {t["function"]["name"]: t["function"] for t in body.get("tools") or []}

    async def tool_events(self) -> list[dict[str, Any]]:
        rows = await self.bench.session.scalars(
            select(RunEvent)
            .where(RunEvent.kind == EventKind.TOOL_CALL)
            .join(Run, Run.id == RunEvent.run_id)
            .order_by(Run.created_at, RunEvent.attempt, RunEvent.seq)
        )
        return [dict(e.content) for e in rows]


async def _resolve(host: str, port: int) -> list[str]:
    """`*.test` is the MCP stub; an address stays itself (the model's stub)."""
    if host.endswith(".test"):
        return ["127.0.0.1"]
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        raise OSError("unknown name") from None


@pytest.fixture
async def ext(
    bench: Bench, mcp_stub: McpStub, secret_key: None, monkeypatch: pytest.MonkeyPatch
) -> Ext:
    monkeypatch.setattr(egress, "_network", mcp_network(mcp_stub, _resolve))
    server = await make_server(bench.people.admin, mcp_stub)
    await approve_as_listed(bench.people.admin, server["id"])
    return Ext(bench, mcp_stub, server)
