"""Module review M8 1, finding 1: the run's name of an external tool (`ext_<12 hex of the tool's id>_<name>`) is
not unique. Tool ids are UUIDv7, whose first 12 hex digits are the millisecond they
were made in, and a refresh makes all of a server's tools in one go; `.` becomes `_`
and the name is cut at 64 characters. A server that lists `get.items` and `get_items`
(or two long names that differ only at the end) gets two tools with one run name: one
`agent_tool` entry then stands for both, and a model's call by that name reaches
whichever the lookup finds first."""

import importlib.util
import uuid
from pathlib import Path
from types import ModuleType

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.modules.agents.journal import renamed
from app.modules.agents.run_models import EventKind, RunEvent, StopReason
from app.modules.agents.toolbox.external import every_external, legacy_name, legacy_names
from app.modules.mcp_servers.models import Classification, McpServerTool, ToolState
from app.runtime.loop import Recorded, ToolCall
from tests.factories_external import Ext, call
from tests.support.mcp_stub import McpStub
from tests.test_run_replay import Crash, die_after, take_up_again

SCHEMA = {"type": "object", "properties": {"q": {"type": "string"}}}
LONG = "repository_branch_protection_rules_for_default_branches_"


def _tools() -> list[dict[str, object]]:
    tools: list[dict[str, object]] = []
    for i in range(10):
        tools.append({"name": f"get.items{i}", "description": "Reads.", "input_schema": SCHEMA})
        tools.append({"name": f"get_items{i}", "description": "Deletes.", "input_schema": SCHEMA})
        tools.append({"name": f"{LONG}read{i}", "description": "Reads.", "input_schema": SCHEMA})
        tools.append({"name": f"{LONG}drop{i}", "description": "Drops.", "input_schema": SCHEMA})
    return tools


async def _refresh(admin: AsyncClient, server_id: str) -> None:
    r = await admin.post(f"/api/ai/mcp-servers/{server_id}/refresh")
    assert r.status_code == 200, r.text


async def test_every_external_tool_has_a_run_name_of_its_own(ext: Ext, mcp_stub: McpStub) -> None:
    """A correct system gives every tool of the organisation a different run name,
    whatever a server calls its tools and whenever their rows were made: a grant and
    a model's call always mean exactly one tool."""
    mcp_stub.state.tools = _tools()
    await _refresh(ext.admin, ext.server["id"])
    tools = await ext.tools()
    assert len(tools) >= 40
    specs = await every_external(ext.bench.session, ext.bench.agent.org_id)
    names = [spec.name for spec, _ in specs]
    doubled = sorted({n for n in names if names.count(n) > 1})
    assert not doubled, f"{len(doubled)} run names stand for two tools, e.g. {doubled[:3]}"


def _migration() -> ModuleType:
    path = next(Path(__file__).parent.parent.glob("alembic/versions/*_f1afc79e3de4_*.py"))
    spec = importlib.util.spec_from_file_location("external_tool_names", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _entries(ext: Ext) -> dict[str, str]:
    rows = await ext.bench.session.execute(
        text("SELECT tool, policy FROM agent_tool WHERE agent_id = :a"), {"a": ext.bench.agent.id}
    )
    return {tool: policy for tool, policy in rows.tuples()}


async def test_an_old_entry_keeps_its_tool_and_an_ambiguous_one_grants_nothing(ext: Ext) -> None:
    """The migration gives an entry under an old name the tool's new name where the
    old one meant exactly one tool; one old name for two tools is given to neither."""
    session, org = ext.bench.session, ext.bench.agent.org_id
    stored = {t.name: t for t in await session.scalars(select(McpServerTool))}
    search = stored["search_issues"]
    twin_ids = [uuid.UUID(f"0123456789ab7{i:03d}8{'0' * 13}{i:02d}") for i in (1, 2)]
    twins = [
        McpServerTool(
            id=twin_ids[i],
            org_id=org,
            server_id=search.server_id,
            name=name,
            description="",
            input_schema={"type": "object"},
            read_only_hint=True,
            fingerprint="f" * 64,
            approved_fingerprint="f" * 64,
            classification=Classification.READ,
            state=ToolState.APPROVED,
        )
        for i, name in enumerate(("get.items", "get_items"))
    ]
    session.add_all(twins)
    await session.flush()
    specs = await every_external(session, org)
    by_id = {spec.remote.tool_id: spec for spec, _ in specs if spec.remote}
    old_search = legacy_name(by_id[search.id].remote)  # type: ignore[arg-type]
    old_twin = legacy_name(by_id[twin_ids[0]].remote)  # type: ignore[arg-type]
    assert old_twin == legacy_name(by_id[twin_ids[1]].remote)  # type: ignore[arg-type]
    for old, policy in ((old_search, "confirm"), (old_twin, "allow")):
        await session.execute(
            text("INSERT INTO agent_tool (org_id, agent_id, tool, policy) VALUES (:o, :a, :t, :p)"),
            {"o": org, "a": ext.bench.agent.id, "t": old, "p": policy},
        )
    await session.execute(text(_migration().TWINS))
    assert await _entries(ext) == {
        old_search: "confirm",
        old_twin: "allow",
        by_id[search.id].name: "confirm",
    }
    old = legacy_names(specs)
    assert old[old_search] == by_id[search.id].name
    assert old_twin not in old


def test_a_journal_of_an_earlier_release_replays_under_the_new_name() -> None:
    """A recorded call under an old name is replayed under the tool's name now; one
    whose old name meant two tools stays as it was (the loop knows no such tool)."""
    steps = [Recorded("", (ToolCall("c1", "ext_0123456789ab_search", {}), ToolCall("c2", "x", {})))]
    names = {"ext_0123456789ab_search": "ext_" + "0" * 32 + "_search"}
    replayed = renamed(steps, names)
    assert [c.name for c in replayed[0].tool_calls] == ["ext_" + "0" * 32 + "_search", "x"]


async def test_a_run_taken_up_again_calls_the_tool_its_old_journal_named(ext: Ext) -> None:
    """A run recorded by an earlier release (the model's call under the tool's old
    name, the worker lost before the call) calls that tool when taken up again."""
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    ext.bench.stub.state.replies.extend([call(name, q="x"), {"content": "Erledigt."}])
    await ext.bench.say("Bitte nachsehen")
    with pytest.MonkeyPatch.context() as dying, pytest.raises(Crash):
        die_after(dying, "after_model_call")
        await ext.bench.run_next()
    session = ext.bench.session
    spec = next(
        s for s, _ in await every_external(session, ext.bench.agent.org_id) if s.name == name
    )
    assert spec.remote is not None
    event = await session.scalar(select(RunEvent).where(RunEvent.kind == EventKind.MODEL_CALL))
    assert event is not None
    content = dict(event.content)
    content["tool_calls"] = [{**c, "name": legacy_name(spec.remote)} for c in content["tool_calls"]]
    event.content = content
    await session.flush()
    assert await take_up_again(ext.bench) == StopReason.COMPLETED
    assert ext.stub.state.calls == [("search_issues", {"q": "x"})]
