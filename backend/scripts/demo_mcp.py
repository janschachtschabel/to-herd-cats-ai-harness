"""MCP in the demo (M8), in "Team Nord", through the public API:

- the organisation's MCP switch on (clients count as data location `external`);
- Anna's personal read token „Claude Code (Demo)" for Team Nord;
- with a model only (a person needs `ai.use` to see agents and to assign one a
  ticket): the external agent „Pipeline" (level 2, Anna responsible, an editor of
  Team Nord) with the write token „CI-Pipeline", and the ticket „Changelog für Release
  1.4 schreiben" that Anna assigns to it: it waits for pick-up;
- with a stub's address only (`--mcp-stub`, never the outside network by default): the
  server „Tracker (Demo)" on it with the shared bearer connector „Tracker-Zugang" (a
  random key, stored encrypted by the installation), its read tool `search_issues`
  approved and its write tool `create_issue` left for an admin to decide.

A token's clear text comes only in the answer that makes it; the demo drops it at once:
it is never printed, logged or kept (`SeededMcp` holds ids and names only). Whoever
wants to use a token makes one of their own in the UI.
"""

import secrets
from dataclasses import dataclass, field

import httpx

from scripts.demo_api import DemoFailed, call

Clients = dict[str, httpx.AsyncClient]
PERSONAL_TOKEN_NAME = "Claude Code (Demo)"  # noqa: S105 -- a name, not a secret
AGENT = "Pipeline"
AGENT_TOKEN_NAME = "CI-Pipeline"  # noqa: S105 -- a name, not a secret
TICKET = "Changelog für Release 1.4 schreiben"
SERVER = "Tracker (Demo)"
CONNECTOR = "Tracker-Zugang"
TOKEN_DAYS = 30


@dataclass
class SeededMcp:
    personal_token_id: str = ""
    agent_id: str | None = None
    agent_token_id: str | None = None
    ticket_number: int | None = None
    server_id: str | None = None
    connector_id: str | None = None
    tools: dict[str, str] = field(default_factory=dict)  # state by tool name


async def switch_on(admin: httpx.AsyncClient) -> None:
    settings = await call(admin, "GET", "/api/ai/mcp")
    body = {"enabled": True, "data_location": "external", "version": settings["version"]}
    await call(admin, "PUT", "/api/ai/mcp", body)


async def _token(client: httpx.AsyncClient, path: str, body: dict[str, object]) -> str:
    """Makes a token and returns its id; the clear text in the answer is dropped here."""
    made = await call(client, "POST", path, body)
    return str(made["id"])


async def personal_token(anna: httpx.AsyncClient, space_id: str) -> str:
    body = {
        "name": PERSONAL_TOKEN_NAME,
        "mode": "read",
        "expires_in_days": TOKEN_DAYS,
        "space_ids": [space_id],
    }
    return await _token(anna, "/api/tokens", body)


async def external_agent(
    admin: httpx.AsyncClient,
    anna: httpx.AsyncClient,
    *,
    ids: dict[str, str],
    space_id: str,
    seeded: SeededMcp,
) -> None:
    agent = await call(
        admin,
        "POST",
        "/api/agents",
        {
            "name": AGENT,
            "kind": "external",
            "intro": "Die Release-Pipeline: holt Tickets über MCP ab und bringt sie zur Prüfung.",
            "responsible_user_id": ids["anna"],
            "status": "active",
            "level": 2,
        },
    )
    seeded.agent_id = str(agent["id"])
    member = {"member_type": "agent", "member_id": seeded.agent_id, "role": "editor"}
    await call(admin, "PUT", f"/api/spaces/{space_id}/members", member)
    body = {"name": AGENT_TOKEN_NAME, "mode": "write", "expires_in_days": TOKEN_DAYS}
    seeded.agent_token_id = await _token(admin, f"/api/agents/{seeded.agent_id}/tokens", body)
    ticket = await call(
        anna,
        "POST",
        f"/api/spaces/{space_id}/tickets",
        {
            "title": TICKET,
            "description_md": "Alle Änderungen seit 1.3 sammeln, nach Bereichen ordnen.",
            "assignee": {"type": "agent", "id": seeded.agent_id},
        },
    )
    if not ticket.get("awaiting_pickup"):
        raise DemoFailed(f"the ticket for {AGENT} does not wait for pick-up")
    seeded.ticket_number = int(ticket["number"])


async def stub_server(admin: httpx.AsyncClient, url: str, seeded: SeededMcp) -> None:
    connector = await call(
        admin,
        "POST",
        "/api/ai/connectors",
        {
            "name": CONNECTOR,
            "auth_kind": "bearer",
            "secret": {"value": secrets.token_urlsafe(24)},
        },
    )
    seeded.connector_id = str(connector["id"])
    server = await call(
        admin,
        "POST",
        "/api/ai/mcp-servers",
        {
            "name": SERVER,
            "url": url,
            "data_location": "local",
            "connector_scope": "shared",
            "connector_id": seeded.connector_id,
            "enabled": True,
        },
    )
    seeded.server_id = str(server["id"])
    if server["refresh"]["status"] != "ok":
        raise DemoFailed(f"reading the tools of {SERVER}: {server['refresh']['status']}")
    tools_path = f"/api/ai/mcp-servers/{seeded.server_id}/tools"
    tools = {t["name"]: t for t in (await call(admin, "GET", f"{tools_path}?limit=100"))["items"]}
    search = tools.get("search_issues")
    if search is None:
        raise DemoFailed(f"{SERVER} lists no tool search_issues")
    if search["classification"] != "read":  # proposed `write` unless the catalogue agrees
        body = {"classification": "read", "version": search["version"], "confirm_loosen": True}
        search = await call(admin, "PATCH", f"{tools_path}/{search['id']}", body)
    approve = {"version": search["version"]}
    await call(admin, "POST", f"{tools_path}/{search['id']}/approve", approve)
    tools = {t["name"]: t for t in (await call(admin, "GET", f"{tools_path}?limit=100"))["items"]}
    seeded.tools = {name: str(tool["state"]) for name, tool in tools.items()}


async def build(
    admin: httpx.AsyncClient,
    people: Clients,
    *,
    ids: dict[str, str],
    space_id: str,
    with_agents: bool,
    mcp_stub: str | None,
) -> SeededMcp:
    seeded = SeededMcp()
    await switch_on(admin)
    seeded.personal_token_id = await personal_token(people["anna"], space_id)
    if with_agents:
        await external_agent(admin, people["anna"], ids=ids, space_id=space_id, seeded=seeded)
    if mcp_stub is not None:
        await stub_server(admin, mcp_stub, seeded)
    return seeded
