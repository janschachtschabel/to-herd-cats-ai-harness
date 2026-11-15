"""Module review M8 1, finding 6: a run judged an external tool by the class it had
when the run was taken up. A tool an admin turns from `read` to `write` while the run
works was still called without a release. Now every call judges the tool as it is."""

from typing import Any

import pytest

from app.modules.agents.run_models import StopReason
from app.modules.agents.step_host import RunHost
from tests.factories_external import Ext, call
from tests.factories_mcp import classify


def _reclassify_after_the_first_answer(ext: Ext, monkeypatch: pytest.MonkeyPatch) -> None:
    original = RunHost.after_model_call

    async def then_reclassify(self: RunHost, step: int, reply: Any) -> None:
        await original(self, step, reply)
        if step == 1:
            tool = (await ext.tools())["search_issues"]
            await classify(ext.admin, ext.server["id"], tool, "write")

    monkeypatch.setattr(RunHost, "after_model_call", then_reclassify)


async def test_a_tool_turned_write_during_a_run_waits_for_a_release(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    await ext.level(4)
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    ext.bench.stub.state.replies.extend([call(name, q="x"), {"content": "Erledigt."}])
    await ext.bench.say("Bitte nachsehen")
    _reclassify_after_the_first_answer(ext, monkeypatch)
    assert await ext.bench.run_next() is None  # waits for Alice's release
    assert ext.stub.state.calls == []


async def test_a_tool_turned_write_beyond_the_agents_level_ends_the_run(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    await ext.grant(search_issues="allow")  # level 2: a write tool is beyond it
    name = await ext.name("search_issues")
    ext.bench.stub.state.replies.extend([call(name, q="x"), {"content": "Erledigt."}])
    await ext.bench.say("Bitte nachsehen")
    _reclassify_after_the_first_answer(ext, monkeypatch)
    assert await ext.bench.run_next() == StopReason.RIGHTS_REVOKED
    assert ext.stub.state.calls == []
