"""Module review M8 2, finding G5: what one agent's external tools add to every model
call is bounded in sum (`toolbox/external_bound.py`). The bound leaves out the same
tools at every step, after a take-up and on replay (name order, greedy); the agent's
grants view says which, and the worker counts them without names."""

import uuid
from typing import Any

import pytest

from app.core.metrics import REGISTRY
from app.modules.agents.run_models import StopReason
from app.modules.agents.toolbox import external_bound
from app.modules.agents.toolbox.base import RemoteTool, ToolContext, ToolSpec
from app.modules.agents.toolbox.external import ExternalArgs, offered_external
from app.runtime.loop import ToolResult
from tests.factories_external import Ext, call
from tests.test_run_replay import Crash, die_after, take_up_again

METRIC = "herd_external_tool_definitions_left_out_total"


def _left_out() -> float:
    return REGISTRY.get_sample_value(METRIC) or 0.0


async def _granted(ext: Ext) -> list[str]:
    """Both tools granted; their run names in name order (the bound's order)."""
    await ext.level(4)
    await ext.grant(search_issues="allow", create_issue="confirm")
    return sorted([await ext.name("search_issues"), await ext.name("create_issue")])


async def _only_the_first_fits(ext: Ext, monkeypatch: pytest.MonkeyPatch) -> None:
    specs = await offered_external(ext.bench.session, ext.bench.agent.org_id)
    sizes = sorted((s.name, external_bound.definition_chars(s)) for s in specs)
    assert len(sizes) == 2
    monkeypatch.setattr(external_bound, "MAX_DEFINITION_CHARS", sizes[0][1] + sizes[1][1] - 1)


async def _shown(ext: Ext) -> dict[str, bool]:
    return {
        t["name"]: t["external"]["left_out"] for t in (await ext.grants())["tools"] if t["external"]
    }


def _spec(name: str, chars: int) -> ToolSpec:
    remote = RemoteTool(uuid.uuid4(), uuid.uuid4(), "Tracker", name, False)
    return ToolSpec(name, "x" * chars, ExternalArgs, _never, remote=remote)


async def _never(ctx: ToolContext, args: Any) -> ToolResult:
    raise AssertionError


def test_the_bound_is_greedy_in_name_order() -> None:
    a, b, c = _spec("ext_a", 50_000), _spec("ext_b", 60_000), _spec("ext_c", 30_000)
    assert external_bound.MAX_DEFINITION_CHARS == 100_000
    for order in ([a, b, c], [c, b, a], [b, a, c]):  # whatever order they come in
        assert external_bound.left_out(order) == {"ext_b"}
    search = ToolSpec("search", "y" * 200_000, ExternalArgs, _never)  # the catalog's
    kept, dropped = external_bound.bounded([search, b, a, c])
    assert [t.name for t in kept] == ["search", "ext_a", "ext_c"] and dropped == 1


async def test_within_the_bound_every_granted_tool_is_offered(ext: Ext) -> None:
    first, second = await _granted(ext)
    assert await _shown(ext) == {first: False, second: False}
    before = _left_out()
    ext.bench.stub.state.replies.append({"content": "Fertig."})
    await ext.bench.say("Hallo")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert {first, second} <= set(ext.offered())
    assert _left_out() == before


async def test_the_same_tool_is_left_out_at_every_step_and_after_a_take_up(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = await _granted(ext)
    await _only_the_first_fits(ext, monkeypatch)
    assert await _shown(ext) == {first: False, second: True}  # the grants view says so
    before = _left_out()
    state = ext.bench.stub.state
    state.replies.extend([call("search", query="Urlaub"), {"content": "Fertig."}])
    await ext.bench.say("Such etwas")
    crash = pytest.MonkeyPatch()
    die_after(crash, "after_model_call")  # the first model call is recorded, then it dies
    with pytest.raises(Crash):
        await ext.bench.run_next()
    crash.undo()
    assert await take_up_again(ext.bench) == StopReason.COMPLETED
    offered = [set(ext.offered(i)) for i in range(len(state.log))]
    assert len(offered) == 2  # the first call is replayed, not asked again
    for names in offered:
        assert first in names and second not in names
    assert "search" in offered[0]  # the catalog's tools are never left out
    assert _left_out() - before == 2  # one per start or take-up, no names


async def test_a_tool_too_large_alone_leaves_room_for_the_next(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = await _granted(ext)
    specs = await offered_external(ext.bench.session, ext.bench.agent.org_id)
    sizes = {s.name: external_bound.definition_chars(s) for s in specs}
    monkeypatch.setattr(external_bound, "MAX_DEFINITION_CHARS", sizes[second])
    if sizes[first] <= sizes[second]:  # the first fits, so the second no longer does
        assert await _shown(ext) == {first: False, second: True}
    else:  # the first is too large on its own: it is left out, the second fits
        assert await _shown(ext) == {first: True, second: False}
