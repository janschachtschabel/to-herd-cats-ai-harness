"""Plan M8 decision 8: an agent gets external tools through its entries, like the
catalog's. The grants list every usable external tool of the organisation (and any
other one the agent has an entry for, as `block`); its default is `block` (an entry
is needed), a read tool is level 2, a write tool level 4 and at most `confirm`. Level
4 is given only by an admin; a personal agent stays at 2."""

import uuid
from typing import Any

from app.modules.agents.toolbox.external import every_external, is_external
from tests.factories_external import Ext


def by_tool(grants: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["external"]["tool_name"]: t for t in grants["tools"] if t["external"]}


async def test_usable_external_tools_are_listed_with_their_server(ext: Ext) -> None:
    grants = await ext.grants()
    assert grants["max_level"] == 4
    shown = by_tool(grants)
    tools = await ext.tools()
    search, create = shown["search_issues"], shown["create_issue"]
    assert search["external"] == {
        "server_id": ext.server["id"],
        "server_name": "Tracker",
        "tool_id": tools["search_issues"]["id"],
        "tool_name": "search_issues",
        "usable": True,
    }
    assert is_external(search["name"]) and len(search["name"]) <= 64
    assert (search["level"], search["effect"], search["default"], search["effective"]) == (
        2,
        "read",
        "block",
        "block",
    )
    assert (create["level"], create["effect"], create["default"]) == (4, "write", "block")
    catalog = [t for t in grants["tools"] if t["external"] is None]
    assert catalog and all(not is_external(t["name"]) for t in catalog)


async def test_entries_name_external_tools(ext: Ext) -> None:
    await ext.grant(search_issues="confirm")
    search = by_tool(await ext.grants())["search_issues"]
    assert (search["entry"], search["effective"]) == ("confirm", "confirm")
    version = (await ext.grants())["version"]
    bad = {"tools": [{"tool": "ext_000000000000_nope", "policy": "allow"}], "version": version}
    r = await ext.admin.put(f"{ext.agent_url}/tools", json=bad)
    assert r.status_code == 422 and r.json()["error"]["code"] == "agent.tool_unknown"


async def test_an_entry_for_a_tool_that_is_not_usable_is_kept_as_block(ext: Ext) -> None:
    await ext.grant(search_issues="allow")
    await ext.patch_server(enabled=False)
    shown = by_tool(await ext.grants())
    assert set(shown) == {"search_issues"}  # the other one has no entry
    search = shown["search_issues"]
    assert search["external"]["usable"] is False
    assert (search["entry"], search["effective"]) == ("allow", "block")
    await ext.grant(search_issues="allow")  # still a known name


async def test_tools_of_another_organisation_are_not_its(ext: Ext) -> None:
    org_id = ext.bench.people.users["admin"].org_id
    names = {spec.name for spec, _ in await every_external(ext.bench.session, org_id)}
    assert await ext.name("search_issues") in names
    assert await every_external(ext.bench.session, uuid.uuid4()) == []


async def test_level_four_only_from_an_admin(ext: Ext) -> None:
    await ext.level(4)
    assert (await ext.grants())["level"] == 4
    r = await ext.bench.people.alice.patch(ext.agent_url, json={"level": 4, "version": 1})
    assert r.status_code == 404  # agents are managed by admins alone
    version = (await ext.grants())["version"]
    r = await ext.admin.patch(ext.agent_url, json={"level": 5, "version": version})
    assert r.status_code == 422


def test_the_policy_of_external_specs() -> None:
    """Without an entry: `block`; a write tool from level 4 on, never looser than
    `confirm`; an entry still tightens."""
    from pydantic import BaseModel

    from app.modules.agents.toolbox.base import Grant, ToolSpec
    from app.modules.agents.toolbox.policy import default_grant, effective

    async def run(ctx: Any, args: Any) -> Any:
        raise AssertionError

    read = ToolSpec("ext_a", "", BaseModel, run, 2, explicit=True)
    write = ToolSpec("ext_b", "", BaseModel, run, 4, floor=Grant.CONFIRM, explicit=True)
    assert default_grant(4, read) == default_grant(4, write) == Grant.BLOCK
    assert effective(4, read, None) == effective(4, write, None) == Grant.BLOCK
    assert effective(2, read, Grant.ALLOW) == Grant.ALLOW
    assert effective(1, read, Grant.ALLOW) == Grant.BLOCK
    assert effective(3, write, Grant.ALLOW) == Grant.BLOCK
    assert effective(4, write, Grant.ALLOW) == Grant.CONFIRM
    assert effective(4, write, Grant.BLOCK) == Grant.BLOCK
