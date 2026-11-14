"""Plan M6 task 2 (decision 2, spec 8.2): the tool catalog with a minimum level and an
effect per tool; an agent's level sets the default grant per tool, its entries
(`agent_tool`) can only tighten it; who may give a level above 2; the run offers only
what is allowed now and stops when a grant is taken away during the run."""

from dataclasses import replace
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.core.principal import SystemRole
from app.modules.agents.models import EventKind, RunEvent, StopReason
from app.modules.agents.step_host import RunHost
from app.modules.agents.toolbox.base import ToolSpec
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.agents.toolbox.policy import (
    Effect,
    Grant,
    default_grant,
    effective,
    may_grant_level,
)
from app.modules.audit.models import AuditLog
from app.modules.spaces.models import SpaceKind
from app.runtime.loop import ToolResult
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace
from tests.test_access import actor_of

AGENTS = "/api/agents"


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


class _Args(BaseModel):
    pass


async def _nothing(ctx: Any, args: Any) -> Any:
    raise AssertionError("never run")


LEVEL_TWO = ToolSpec("probe", "-", _Args, _nothing, level=2, effect=Effect.PROPOSE)


@pytest.mark.parametrize(
    ("level", "entry", "expected"),
    [
        (1, None, Grant.BLOCK),  # below the tool's level: blocked
        (1, Grant.ALLOW, Grant.BLOCK),  # an entry cannot loosen
        (1, Grant.CONFIRM, Grant.BLOCK),
        (2, None, Grant.ALLOW),
        (2, Grant.ALLOW, Grant.ALLOW),
        (2, Grant.CONFIRM, Grant.CONFIRM),
        (2, Grant.BLOCK, Grant.BLOCK),
        (3, None, Grant.ALLOW),
        (3, Grant.CONFIRM, Grant.CONFIRM),
        (3, Grant.BLOCK, Grant.BLOCK),
    ],
)
def test_the_grant_is_the_stricter_of_level_and_entry(
    level: int, entry: Grant | None, expected: Grant
) -> None:
    assert effective(level, LEVEL_TWO, entry) == expected
    assert default_grant(level, LEVEL_TWO) == (Grant.ALLOW if level >= 2 else Grant.BLOCK)


def test_every_tool_has_a_level_and_an_effect() -> None:
    assert CATALOG, "the catalog lists tools"
    for spec in CATALOG.values():
        assert spec.level in (1, 2, 3), spec.name
        assert spec.effect in set(Effect), spec.name
        assert spec.effect != Effect.READ or spec.level == 1, spec.name
    for name in ("search", "read_page", "read_ticket"):
        assert (CATALOG[name].level, CATALOG[name].effect) == (1, Effect.READ)


async def test_a_new_agent_is_level_two_and_level_four_is_not_offered(bench: Bench) -> None:
    body = {
        "name": "Bea",
        "connection_id": str(bench.connection.id),
        "model": "m1",
        "responsible_user_id": bench.people.id("admin"),
    }
    created = await bench.people.admin.post(AGENTS, json=body)
    assert created.status_code == 201 and created.json()["level"] == 2
    agent = created.json()
    url = f"{AGENTS}/{agent['id']}"
    four = await bench.people.admin.patch(url, json={"level": 4, "version": 1})
    assert four.status_code == 422
    three = await bench.people.admin.patch(url, json={"level": 3, "version": 1})
    assert three.status_code == 200 and three.json()["level"] == 3


async def test_the_tools_of_an_agent(bench: Bench) -> None:
    url = f"{AGENTS}/{bench.agent.id}/tools"
    shown = await bench.people.admin.get(url)
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert (body["level"], body["version"]) == (2, bench.agent.version)
    tools = {t["name"]: t for t in body["tools"]}
    assert set(tools) == set(CATALOG)
    assert tools["search"] == {
        "name": "search",
        "level": 1,
        "effect": "read",
        "default": "allow",
        "entry": None,
        "effective": "allow",
    }
    put = {"tools": [{"tool": "read_page", "policy": "block"}], "version": body["version"]}
    changed = await bench.people.admin.put(url, json=put)
    assert changed.status_code == 200, changed.text
    after = {t["name"]: t for t in changed.json()["tools"]}
    assert (after["read_page"]["entry"], after["read_page"]["effective"]) == ("block", "block")
    assert changed.json()["version"] == body["version"] + 1
    stale = await bench.people.admin.put(url, json=put)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "agent.version_conflict"
    audit = await bench.session.scalar(
        select(AuditLog).where(AuditLog.action == "agent.tools_changed")
    )
    assert audit is not None and audit.details == {"tools": {"read_page": "block"}}
    cleared = await bench.people.admin.put(url, json={"tools": [], "version": body["version"] + 1})
    assert {t["name"]: t["entry"] for t in cleared.json()["tools"]}["read_page"] is None


@pytest.mark.parametrize(
    ("tools", "code"),
    [
        ([{"tool": "delete_page", "policy": "block"}], "agent.tool_unknown"),
        ([{"tool": "search", "policy": "block"}, {"tool": "search", "policy": "allow"}], None),
        ([{"tool": "search", "policy": "maybe"}], None),
    ],
)
async def test_what_the_tools_take(bench: Bench, tools: list[Any], code: str | None) -> None:
    url = f"{AGENTS}/{bench.agent.id}/tools"
    r = await bench.people.admin.put(url, json={"tools": tools, "version": bench.agent.version})
    assert r.status_code == 422, r.text
    if code:
        assert r.json()["error"]["code"] == code


async def test_only_agent_managers_see_and_set_tools(bench: Bench) -> None:
    url = f"{AGENTS}/{bench.agent.id}/tools"
    for who in ("alice", "gast"):
        client = getattr(bench.people, who)
        assert (await client.get(url)).status_code == 404
        put = {"tools": [], "version": bench.agent.version}
        r = await client.put(url, json=put)
        assert r.status_code == 404 and r.json()["error"]["code"] == "agent.not_found"


async def test_who_may_give_a_level_above_two(
    bench: Bench, make_space: MakeSpace, make_user: Any
) -> None:
    """Spec 8.2: whoever manages every space of the agent, or an admin. Org agents
    need `agent.manage` (owner, admin) to be changed at all, so through the API only
    admins ever get here; the rule itself is held to both conditions."""
    session = bench.session
    lead = await make_user(SystemRole.MEMBER)
    a = await make_space(SpaceKind.TEAM, members=[(lead, SpaceRole.ADMIN)])
    b = await make_space(SpaceKind.TEAM, members=[(lead, SpaceRole.EDITOR)])
    leader = await actor_of(session, lead)
    admin = await actor_of(session, bench.people.users["admin"])
    agent = bench.agent
    assert await may_grant_level(session, leader, agent.id, 2)  # up to 2: no question
    assert not await may_grant_level(session, leader, agent.id, 3)  # an agent without spaces
    await bench.join(a)
    assert await may_grant_level(session, leader, agent.id, 3)  # manages its one space
    await bench.join(b)
    assert not await may_grant_level(session, leader, agent.id, 3)  # not b
    assert await may_grant_level(session, admin, agent.id, 3)
    # Through the API the space admin is no agent manager: 404 before the level rule.
    r = await bench.people.alice.patch(
        f"{AGENTS}/{agent.id}", json={"level": 3, "version": agent.version}
    )
    assert r.status_code == 404


async def test_a_run_offers_only_what_is_allowed(bench: Bench) -> None:
    url = f"{AGENTS}/{bench.agent.id}/tools"
    put = {
        "tools": [
            {"tool": "read_page", "policy": "block"},
            {"tool": "search", "policy": "confirm"},
        ],
        "version": bench.agent.version,
    }
    assert (await bench.people.admin.put(url, json=put)).status_code == 200
    bench.stub.state.replies.extend(
        [call("read_page", page_id="00000000-0000-0000-0000-000000000000"), {"content": "ok"}]
    )
    await bench.say("Read")
    assert await bench.run_next() == StopReason.COMPLETED
    offered = [t["function"]["name"] for t in bench.stub.state.log[0].body.get("tools", [])]
    assert offered == [n for n in CATALOG if n not in ("read_page", "search")]
    assert "search" not in offered  # `confirm` waits for the release flow (task 7)
    tool_events = await bench.session.scalars(
        select(RunEvent).where(RunEvent.kind == EventKind.TOOL_CALL)
    )
    assert list(tool_events) == []  # the blocked call never ran
    assert "unknown tool" in bench.stub.state.texts()


async def test_a_tool_the_catalog_does_not_know_never_runs(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench.stub.state.replies.extend([call("delete_page", page_id="x"), {"content": "ok"}])
    await bench.say("Delete")
    assert await bench.run_next() == StopReason.COMPLETED
    assert "unknown tool 'delete_page'" in bench.stub.state.texts()


async def test_a_grant_taken_away_during_the_run_stops_it(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench.stub.state.replies.extend([call("search", query="x"), {"content": "never"}])
    await bench.say("Find")
    original = RunHost.after_model_call

    async def lowered(self: RunHost, step: int, reply: Any) -> None:
        await original(self, step, reply)
        url = f"{AGENTS}/{bench.agent.id}/tools"
        version = (await bench.people.admin.get(url)).json()["version"]
        put = {"tools": [{"tool": "search", "policy": "block"}], "version": version}
        assert (await bench.people.admin.put(url, json=put)).status_code == 200

    monkeypatch.setattr(RunHost, "after_model_call", lowered)
    assert await bench.run_next() == StopReason.RIGHTS_REVOKED
    assert len(bench.stub.state.log) == 1


async def test_a_lower_level_during_the_run_stops_it(
    bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = replace(LEVEL_TWO, name="probe_two", run=_answer)
    monkeypatch.setitem(CATALOG, "probe_two", probe)
    bench.stub.state.replies.extend([call("probe_two"), {"content": "never"}])
    await bench.say("Go")
    original = RunHost.after_model_call

    async def lowered(self: RunHost, step: int, reply: Any) -> None:
        await original(self, step, reply)
        bench.agent.level = 1
        await bench.session.flush()

    monkeypatch.setattr(RunHost, "after_model_call", lowered)
    assert await bench.run_next() == StopReason.RIGHTS_REVOKED


async def _answer(ctx: Any, args: Any) -> Any:
    return ToolResult("probe", "done")
