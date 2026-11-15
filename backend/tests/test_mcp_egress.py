"""External MCP servers behind the egress guard (plan M8 review focus 3): names are
resolved and checked at every connection, private and metadata addresses are never
dialled, redirects to other hosts are not followed, the SDK's own log lines stay out
of the logs."""

import logging

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import egress
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.modules.mcp_servers.calls import ToolCaller
from app.modules.mcp_servers.errors import RemoteFailed
from tests.factories_dms import People
from tests.factories_mcp import SERVERS, approve, make_server, mcp_network, tools_of
from tests.support.mcp_stub import McpStub


async def test_a_name_that_turns_private_after_creation_is_refused(
    ai_people: People, mcp_stub: McpStub, monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """DNS rebinding: the name answered the stub's address when the server was created
    and a private one later; every connection resolves anew and checks the answer, so
    the refresh and the call stop at the guard."""
    answers = {"now": ["127.0.0.1"]}

    async def rebinding(host: str, port: int) -> list[str]:
        return answers["now"]

    monkeypatch.setattr(egress, "_network", mcp_network(mcp_stub, rebinding))
    made = await make_server(ai_people.admin, mcp_stub)
    assert made["refresh"]["status"] == "ok"
    tool = (await tools_of(ai_people.admin, made["id"]))["search_issues"]
    await approve(ai_people.admin, made["id"], tool)
    answers["now"] = ["10.1.2.3"]
    mcp_stub.state.log.clear()
    refreshed = await ai_people.admin.post(f"{SERVERS}/{made['id']}/refresh", json={})
    assert refreshed.json()["status"] == "blocked"
    alice = ai_people.users["alice"]
    with pytest.raises(RemoteFailed) as caught:
        await ToolCaller(session).call_tool(
            alice.org_id, made["id"], "search_issues", {}, on_behalf_of=alice.id
        )
    assert caught.value.status == "blocked"
    answers["now"] = ["169.254.169.254"]
    tested = await ai_people.admin.post(f"{SERVERS}/{made['id']}/test", json={})
    assert tested.json()["status"] == "blocked"
    assert mcp_stub.state.log == []


async def test_a_redirect_to_a_private_address_is_not_followed(
    ai_people: People, mcp_egress: McpStub
) -> None:
    made = await make_server(ai_people.admin, mcp_egress)
    mcp_egress.state.redirect_to = "https://10.0.0.1/mcp"
    refreshed = await ai_people.admin.post(f"{SERVERS}/{made['id']}/refresh", json={})
    assert refreshed.json()["status"] == "redirect"
    assert all(r.path == "/mcp" for r in mcp_egress.state.log)
    assert len(await tools_of(ai_people.admin, made["id"])) == 2  # nothing was changed


async def test_a_slow_listing_times_out(
    ai_people: People, mcp_egress: McpStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.mcp_servers import tools as tool_service

    made = await make_server(ai_people.admin, mcp_egress)
    monkeypatch.setattr(tool_service, "LIST_TIMEOUT_SECONDS", 0.5)
    mcp_egress.state.delay = 2
    refreshed = await ai_people.admin.post(f"{SERVERS}/{made['id']}/refresh", json={})
    assert refreshed.json()["status"] == "timeout"


async def test_a_huge_tool_list_is_refused(
    ai_people: People, mcp_egress: McpStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.mcp_servers import tools as tool_service

    monkeypatch.setattr(tool_service, "MAX_LIST_BYTES", 20_000)
    mcp_egress.state.tools = [{"name": f"t{n}", "description": "x" * 1000} for n in range(100)]
    made = await make_server(ai_people.admin, mcp_egress)
    assert made["refresh"]["status"] == "too_large"
    assert await tools_of(ai_people.admin, made["id"]) == {}


def test_the_sdks_own_log_lines_are_silenced() -> None:
    """Its error lines may quote what a server answered (a tool's result)."""
    configure_logging(get_settings())
    for name in ("mcp", "mcp.client.streamable_http", "mcp.client.session"):
        assert not logging.getLogger(name).isEnabledFor(logging.CRITICAL)
