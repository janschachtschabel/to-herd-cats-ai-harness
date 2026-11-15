"""Plan M8 task 13: every external tool call of a run counts once in
`herd_external_tool_calls_total{outcome, effect}`, after its step committed (ids and
codes only: no server, tool name or argument as a label). A run sends at most
`HERD_MCP_MAX_CALLS_PER_RUN` calls; the next one is refused as a result (`limited`),
nothing is sent and the run goes on."""

from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.metrics import REGISTRY
from app.modules.agents import external_step
from app.modules.agents.external_repository import sent_calls
from app.modules.agents.run_models import EventKind, RunEvent, StopReason
from app.modules.agents.toolbox.external import CALL_LIMIT, OUTCOME_UNKNOWN, POLICY_REFUSED
from app.modules.mcp_servers import calls
from tests.factories_external import Ext, call
from tests.test_run_external_tools import ask
from tests.test_run_external_writes import asked, decide


def _count(outcome: str, effect: str = "read") -> float:
    labels = {"outcome": outcome, "effect": effect}
    return REGISTRY.get_sample_value("herd_external_tool_calls_total", labels) or 0.0


class _Before:
    def __init__(self) -> None:
        self.values = {
            o: _count(o)
            for o in ("ok", "error", "failed", "timeout", "refused", "limited", "unknown")
        }

    def delta(self, outcome: str) -> float:
        return _count(outcome) - self.values[outcome]


async def test_each_outcome_counts_once(ext: Ext, monkeypatch: pytest.MonkeyPatch) -> None:
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    before = _Before()
    ext.stub.state.results["search_issues"] = {"text": "Issue 7"}
    assert await ask(ext, call(name, q="a")) == StopReason.COMPLETED
    ext.stub.state.results["search_issues"] = {"text": "kaputt", "is_error": True}
    assert await ask(ext, call(name, q="b")) == StopReason.COMPLETED
    ext.stub.state.results.clear()
    ext.stub.state.failures.extend([500, 500, 500])
    assert await ask(ext, call(name, q="c")) == StopReason.COMPLETED
    ext.stub.state.failures.clear()
    monkeypatch.setattr(calls, "CALL_TIMEOUT_SECONDS", 0.5)
    ext.stub.state.delay = 2
    assert await ask(ext, call(name, q="d")) == StopReason.COMPLETED
    ext.stub.state.delay = 0
    assert {o: before.delta(o) for o in before.values} == {
        "ok": 1,
        "error": 1,
        "failed": 1,
        "timeout": 1,
        "refused": 0,
        "limited": 0,
        "unknown": 0,
    }
    texts = [e["text"] for e in await ext.tool_events()]  # by seq: runs interleave
    assert any(t.endswith("(timeout).") for t in texts)


async def test_a_call_not_sent_for_a_rule_counts_as_refused(ext: Ext) -> None:
    await ext.patch_server(connector_scope="personal")
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    before = _Before()
    assert await ask(ext, call(name, q="x")) == StopReason.COMPLETED
    assert ext.stub.state.calls == []
    assert before.delta("refused") == 1 and before.delta("ok") == 0


async def test_a_write_tool_counts_with_its_effect_once_released(ext: Ext) -> None:
    """A write tool waits for its release: nothing counts while it waits."""
    written = {o: _count(o, "write") for o in ("ok", "refused")}
    approval = await asked(ext, title="x")
    assert _count("ok", "write") == written["ok"]
    assert _count("refused", "write") == written["refused"]
    r = await decide(ext, approval, "approve")
    assert r.status_code == 200, r.text
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert _count("ok", "write") == written["ok"] + 1


async def test_the_run_sends_at_most_the_cap(ext: Ext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "mcp_max_calls_per_run", 2)
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    before = _Before()
    replies: list[dict[str, Any]] = [call(name, q=q) for q in ("a", "b", "c")]
    assert await ask(ext, *replies) == StopReason.COMPLETED
    assert ext.stub.state.calls == [("search_issues", {"q": "a"}), ("search_issues", {"q": "b"})]
    assert before.delta("ok") == 2 and before.delta("limited") == 1
    last = (await ext.tool_events())[-1]
    assert last["text"] == CALL_LIMIT.format(limit=2)
    assert last["args"] == {"q": "c"}
    # A new run has its own count.
    assert await ask(ext, call(name, q="d")) == StopReason.COMPLETED
    assert ext.stub.state.calls[-1] == ("search_issues", {"q": "d"})


async def test_the_cap_counts_by_the_journal_mark_not_by_text(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Module review M8 1, finding 14: a server answering exactly the placeholder's text
    does not count twice; an entry recorded before the mark still counts."""
    monkeypatch.setattr(get_settings(), "mcp_max_calls_per_run", 2)
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    ext.stub.state.results["search_issues"] = {"text": OUTCOME_UNKNOWN}
    assert await ask(ext, call(name, q="a"), call(name, q="b")) == StopReason.COMPLETED
    assert [args for _, args in ext.stub.state.calls] == [{"q": "a"}, {"q": "b"}]
    run_id = (await ext.bench.session.scalars(select(RunEvent.run_id))).first()
    assert run_id is not None
    org_id = ext.bench.people.users["alice"].org_id
    assert await sent_calls(ext.bench.session, org_id, run_id) == 2
    ext.bench.session.add(  # as the release before the mark wrote it
        RunEvent(
            org_id=org_id,
            run_id=run_id,
            attempt=1,
            seq=999,
            kind=EventKind.TOOL_CALL,
            content={"name": name, "text": OUTCOME_UNKNOWN, "source": "external"},
        )
    )
    await ext.bench.session.flush()
    assert await sent_calls(ext.bench.session, org_id, run_id) == 3


async def test_policy_refusals_do_not_use_up_the_cap(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cap counts calls sent: a call the policy kept back is not one."""
    monkeypatch.setattr(get_settings(), "mcp_max_calls_per_run", 1)
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    real_allows = external_step.policy_allows
    refusals = iter([False])

    async def allows(*args: Any, **kwargs: Any) -> bool:
        return next(refusals, True) and await real_allows(*args, **kwargs)

    monkeypatch.setattr(external_step, "policy_allows", allows)
    assert await ask(ext, call(name, q="a"), call(name, q="b")) == StopReason.COMPLETED
    texts = [e["text"] for e in await ext.tool_events()]
    assert texts[0] == POLICY_REFUSED
    assert ext.stub.state.calls == [("search_issues", {"q": "b"})]


class _TimedOut(Exception):
    sqlstate = "57014"


async def test_an_unrecorded_result_counts_as_unknown(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The call was sent, but its result could not be recorded in time: the first
    entry stands, and the call counts as `unknown`."""
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    before = _Before()

    async def late(*args: Any, **kwargs: Any) -> Any:
        raise _TimedOut()

    monkeypatch.setattr(external_step, "_after", late)
    assert await ask(ext, call(name, q="x")) == StopReason.COMPLETED
    assert ext.stub.state.calls == [("search_issues", {"q": "x"})]
    assert (await ext.tool_events())[-1]["text"] == OUTCOME_UNKNOWN
    assert before.delta("unknown") == 1 and before.delta("ok") == 0


@pytest.mark.parametrize("limit", [0, 501])
def test_the_cap_has_bounds(limit: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERD_MCP_MAX_CALLS_PER_RUN", str(limit))
    with pytest.raises(ValidationError):
        Settings()


def test_the_cap_is_20_by_default() -> None:
    assert get_settings().mcp_max_calls_per_run == 20
