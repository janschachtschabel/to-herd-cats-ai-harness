"""Plan M6 task 11: what the agent administration needs besides the tools themselves.
`max_level` in an agent's tools tells the caller the highest level they may give it
(so a level they may not give is never offered), and `GET /api/agents/{id}/spaces`
lists the spaces the agent is a member of, with its role there, by name."""

from typing import Any

from app.core.permissions import SpaceRole
from app.core.principal import SystemRole
from app.modules.agents.grants import GrantService
from app.modules.spaces.models import SpaceKind
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace
from tests.test_access import actor_of

AGENTS = "/api/agents"


async def test_an_admin_may_give_level_four(bench: Bench) -> None:
    r = await bench.people.admin.get(f"{AGENTS}/{bench.agent.id}/tools")
    assert r.status_code == 200, r.text
    assert r.json()["max_level"] == 4  # acting outside (plan M8 decision 8)


async def test_max_level_follows_the_level_rule(
    bench: Bench, make_space: MakeSpace, make_user: Any
) -> None:
    """Above 2 only admins (through the API only admins manage agents at all): someone
    who manages every space of the agent is offered 2."""
    session = bench.session
    lead = await make_user(SystemRole.MEMBER)
    a = await make_space(SpaceKind.TEAM, members=[(lead, SpaceRole.ADMIN)])
    leader = await actor_of(session, lead)
    admin = await actor_of(session, bench.people.users["admin"])
    grants = GrantService(session)
    await bench.join(a)
    assert grants.max_level(leader, bench.agent) == 2
    assert grants.max_level(admin, bench.agent) == 4


async def test_the_spaces_of_an_agent(bench: Bench, make_space: MakeSpace) -> None:
    zebra = await make_space(SpaceKind.TEAM, name="Zebra")
    apfel = await make_space(SpaceKind.OPEN, name="Apfel")
    await make_space(SpaceKind.TEAM, name="Mitte")  # not the agent's
    await bench.join(zebra, SpaceRole.EDITOR)
    await bench.join(apfel)
    url = f"{AGENTS}/{bench.agent.id}/spaces"
    first = await bench.people.admin.get(url, params={"limit": 1})
    assert first.status_code == 200, first.text
    body = first.json()
    assert [(s["name"], s["kind"], s["role"]) for s in body["items"]] == [
        ("Apfel", "open", "viewer")
    ]
    assert body["items"][0]["id"] == str(apfel.id)
    rest = await bench.people.admin.get(url, params={"limit": 1, "cursor": body["next_cursor"]})
    assert [(s["name"], s["role"]) for s in rest.json()["items"]] == [("Zebra", "editor")]
    assert rest.json()["next_cursor"] is None


async def test_only_agent_managers_see_its_spaces(bench: Bench) -> None:
    url = f"{AGENTS}/{bench.agent.id}/spaces"
    for who in ("alice", "gast"):
        r = await getattr(bench.people, who).get(url)
        assert r.status_code == 404 and r.json()["error"]["code"] == "agent.not_found"
    unknown = await bench.people.admin.get(f"{AGENTS}/{bench.dm_id}/spaces")
    assert unknown.status_code == 404
