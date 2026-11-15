"""Plan M8 task 10: what the agents' screens need to show an external agent rightly.
Its grants offer at most level 2 to anyone (also to an admin) and say which catalog
tools can reach its token over `/mcp` (`via_mcp`); the directory names every agent's
kind, so pickers can mark an external one (it answers nothing by itself)."""

from typing import Any

from httpx import AsyncClient

from tests.factories_external_agents import make_external
from tests.factories_writing import Work

# The catalog tools `/mcp` offers that an external agent (level 2 at most) can get.
REACHABLE = {
    "search",
    "read_page",
    "read_ticket",
    "list_tree",
    "list_versions",
    "search_tickets",
    "propose_page_change",
    "propose_new_page",
    "comment_ticket",
    "set_ticket_status",
    "create_ticket",
    "link_ticket_page",
}


async def _grants(client: AsyncClient, agent_id: object) -> dict[str, Any]:
    r = await client.get(f"/api/agents/{agent_id}/tools")
    assert r.status_code == 200, r.text
    shown: dict[str, Any] = r.json()
    return shown


async def test_an_external_agents_grants_offer_level_two_at_most(work: Work) -> None:
    agent = await make_external(work)
    assert (await _grants(work.admin, agent.id))["max_level"] == 2
    internal = await _grants(work.admin, work.bench.agent.id)
    assert internal["max_level"] == 4  # an admin may give an internal agent level 4


async def test_grants_say_which_tools_reach_an_external_agents_token(work: Work) -> None:
    agent = await make_external(work)
    tools = (await _grants(work.admin, agent.id))["tools"]
    assert {t["name"] for t in tools if t["via_mcp"]} == REACHABLE
    assert not any(t["via_mcp"] for t in tools if t["name"] in {"ask_user", "update_page"})
    internal = (await _grants(work.admin, work.bench.agent.id))["tools"]
    assert not any(t["via_mcp"] for t in internal)


async def test_the_directory_names_each_agents_kind(work: Work) -> None:
    agent = await make_external(work)
    r = await work.bench.people.alice.get(
        "/api/directory", params={"space_id": str(work.space.id), "limit": 100}
    )
    assert r.status_code == 200, r.text
    kinds = {e["id"]: e["kind"] for e in r.json()["items"]}
    assert kinds[str(agent.id)] == "external"
    assert kinds[str(work.bench.agent.id)] == "internal"
    alice = str(work.bench.people.users["alice"].id)
    assert kinds[alice] is None  # people and groups have no kind
