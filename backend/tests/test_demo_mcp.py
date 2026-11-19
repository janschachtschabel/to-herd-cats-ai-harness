"""The demo's MCP part (scripts/demo_mcp.py): the switch on and Anna's read token for
Team Nord in every demo; with a model the external agent „Pipeline" with its write
token and a ticket waiting for pick-up; with a stub's address a server with a shared
connector, its read tool approved and its write tool open. No token's clear text is
kept or printed."""

from collections.abc import Awaitable, Callable
from typing import Any

from httpx import AsyncClient

from app.modules.users.models import User
from scripts import demo_mcp
from scripts.demo_seed import main
from tests.factories import PASSWORD, login
from tests.support.mcp_stub import McpStub
from tests.test_demo_ai import demo as demo_with_ai  # noqa: F401 -- the fixture
from tests.test_demo_seed import demo  # noqa: F401 -- the fixture


async def _get(client: AsyncClient, path: str) -> Any:
    response = await client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


async def test_mcp_is_on_and_anna_has_a_read_token_for_team_nord(demo: dict[str, Any]) -> None:  # noqa: F811
    seeded, anna = demo["seeded"], demo["clients"]["anna"]
    me = await _get(anna, "/api/auth/me")
    assert "mcp.use" in me["permissions"]
    tokens = (await _get(anna, "/api/tokens?limit=100"))["items"]
    assert [(t["name"], t["mode"], t["kind"]) for t in tokens] == [
        (demo_mcp.PERSONAL_TOKEN_NAME, "read", "personal")
    ]
    assert tokens[0]["space_ids"] == [seeded.space_id]
    assert str(tokens[0]["id"]) == seeded.mcp.personal_token_id
    # Without a model there is no agent to see or assign, so no external one either.
    assert seeded.mcp.agent_id is None
    assert seeded.mcp.server_id is None
    assert "herd_" not in repr(seeded)


async def test_with_a_model_an_external_agent_has_a_token_and_a_ticket_to_pick_up(
    demo_with_ai: dict[str, Any],  # noqa: F811
) -> None:
    seeded, admin, anna = (
        demo_with_ai["seeded"],
        demo_with_ai["admin"],
        demo_with_ai["clients"]["anna"],
    )
    mcp = seeded.mcp
    agent = await _get(admin, f"/api/agents/{mcp.agent_id}")
    assert (agent["name"], agent["kind"], agent["level"]) == (demo_mcp.AGENT, "external", 2)
    tokens = (await _get(admin, f"/api/agents/{mcp.agent_id}/tokens?limit=100"))["items"]
    assert [(t["name"], t["mode"]) for t in tokens] == [(demo_mcp.AGENT_TOKEN_NAME, "write")]
    ticket = await _get(anna, f"/api/tickets/{mcp.ticket_number}")
    assert ticket["title"] == demo_mcp.TICKET
    assert ticket["assignee"]["id"] == mcp.agent_id
    assert ticket["awaiting_pickup"] is True
    assert ticket["status"]["category"] == "open"
    assert "herd_" not in repr(seeded)


async def test_with_a_stub_a_server_with_a_shared_connector_and_one_tool_approved(
    make_client: Callable[..., Awaitable[AsyncClient]],
    owner_user: User,
    mcp_egress: McpStub,
    secret_key: None,
) -> None:
    admin = await make_client(csrf=True)
    await login(admin, owner_user.email, PASSWORD)
    seeded = demo_mcp.SeededMcp()
    await demo_mcp.stub_server(admin, mcp_egress.url, seeded)
    assert seeded.tools == {"search_issues": "approved", "create_issue": "pending"}
    server = await _get(admin, f"/api/ai/mcp-servers/{seeded.server_id}")
    assert (server["name"], server["connector_scope"]) == (demo_mcp.SERVER, "shared")
    connector = await _get(admin, f"/api/ai/connectors/{seeded.connector_id}")
    assert (connector["name"], connector["has_secret"]) == (demo_mcp.CONNECTOR, True)
    # The connector's key went to the stub as a bearer token, and nowhere else here.
    assert any(
        "bearer " in r.headers.get("authorization", "").lower() for r in mcp_egress.state.log
    )


def test_the_seed_takes_a_stub_address_by_argument(monkeypatch: Any) -> None:
    seen: dict[str, Any] = {}

    async def fake_main(
        base: str, admin_email: str, mcp_stub: str | None, oidc_stub: str | None, *_: Any
    ) -> int:
        seen.update(base=base, admin=admin_email, mcp_stub=mcp_stub)
        return 0

    monkeypatch.setattr("scripts.demo_seed._main", fake_main)
    assert main(["--admin", "a@example.com", "--mcp-stub", "https://localhost:9/mcp"]) == 0
    assert seen["mcp_stub"] == "https://localhost:9/mcp"
    assert main(["--admin", "a@example.com"]) == 0
    assert seen["mcp_stub"] is None
