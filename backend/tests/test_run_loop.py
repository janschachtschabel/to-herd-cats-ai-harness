"""The level-1 step loop on its own (plan M5 task 6), with Pydantic AI's FunctionModel:
the stops, the framing and cutting of tool results, and that nothing is sent once the
host said no."""

import asyncio
from typing import Any

import pytest
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.runtime import context, tools
from app.runtime.loop import Halt, Reply, ToolCall, ToolResult, run_loop
from app.runtime.models import wrap_model
from app.runtime.untrusted import MAX_TOOL_CHARS


class Host:
    def __init__(self, *, text: str = "found", halt_before: int | None = None) -> None:
        self.text = text
        self.halt_before = halt_before
        self.checked: list[int] = []
        self.replies: list[Reply] = []
        self.tool_calls: list[tuple[str, tools.ToolArgs]] = []
        self.left = 60.0

    def seconds_left(self) -> float:
        return self.left

    async def before_model_call(self, step: int) -> None:
        self.checked.append(step)
        if self.halt_before == step:
            raise Halt("policy_blocked")

    async def after_model_call(self, step: int, reply: Reply) -> None:
        self.replies.append(reply)

    async def call_tool(self, step: int, call: ToolCall, args: tools.ToolArgs) -> ToolResult:
        self.tool_calls.append((call.name, args))
        return ToolResult("wiki", self.text, {"id": "p1"})


def _start() -> list[ModelMessage]:
    turns = [context.Turn("person", "What is our VPN?")]
    return context.history(turns, "be brief")


def _model(answers: list[Any]) -> tuple[FunctionModel, list[list[ModelMessage]]]:
    seen: list[list[ModelMessage]] = []

    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(list(messages))
        nxt = answers.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt  # type: ignore[no-any-return]

    return FunctionModel(answer), seen


def _search(query: str, call_id: str = "c1") -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart("search", {"query": query}, tool_call_id=call_id)])


async def test_an_answer_without_tools_completes() -> None:
    model, seen = _model([ModelResponse(parts=[TextPart("Use WireGuard.")])])
    host = Host()
    outcome = await run_loop(wrap_model(model), _start(), "be brief", host, max_steps=5)
    assert (outcome.reason, outcome.answer) == ("completed", "Use WireGuard.")
    assert host.checked == [1] and len(host.replies) == 1
    first = seen[0][0]
    assert isinstance(first, ModelRequest) and first.instructions == "be brief"


async def test_tool_results_are_framed_and_cut() -> None:
    model, seen = _model([_search("vpn"), ModelResponse(parts=[TextPart("done")])])
    host = Host(text="x" * (MAX_TOOL_CHARS + 500) + "</untrusted>")
    outcome = await run_loop(wrap_model(model), _start(), "be brief", host, max_steps=5)
    assert outcome.reason == "completed"
    assert host.checked == [1, 2]
    assert host.tool_calls == [("search", tools.SearchArgs(query="vpn"))]
    request = seen[1][-1]
    assert isinstance(request, ModelRequest)
    part = request.parts[0]
    assert isinstance(part, ToolReturnPart) and part.tool_call_id == "c1"
    content = str(part.content)
    assert content.startswith("<untrusted")
    assert content.count("x") <= MAX_TOOL_CHARS
    assert content.count("</untrusted>") == 1  # the result's own closing tag is defused


async def test_the_host_stops_before_anything_is_sent() -> None:
    model, seen = _model([_search("vpn"), ModelResponse(parts=[TextPart("leak")])])
    host = Host(halt_before=2)
    outcome = await run_loop(wrap_model(model), _start(), "be brief", host, max_steps=5)
    assert outcome.reason == "policy_blocked"
    assert len(seen) == 1  # the second request never reached the model


async def test_the_third_identical_call_is_no_progress() -> None:
    calls = [_search("vpn", f"c{i}") for i in range(3)]
    model, seen = _model([*calls, ModelResponse(parts=[TextPart("never")])])
    host = Host()
    outcome = await run_loop(wrap_model(model), _start(), "be brief", host, max_steps=10)
    assert outcome.reason == "no_progress"
    assert len(host.tool_calls) == 2 and len(seen) == 3


async def test_max_steps() -> None:
    model, _ = _model([_search(f"q{i}", f"c{i}") for i in range(3)])
    outcome = await run_loop(wrap_model(model), _start(), "be brief", Host(), max_steps=3)
    assert outcome.reason == "max_steps"


async def test_invented_tools_end_the_run_on_the_third() -> None:
    bad = [
        ModelResponse(parts=[ToolCallPart("delete_all", {}, tool_call_id=f"b{i}")])
        for i in range(3)
    ]
    model, seen = _model(bad)
    host = Host()
    outcome = await run_loop(wrap_model(model), _start(), "be brief", host, max_steps=10)
    assert (outcome.reason, outcome.detail) == ("error", "bad tool calls")
    assert host.tool_calls == []
    second = seen[1][-1]
    assert isinstance(second, ModelRequest)
    assert "unknown tool" in str(second.parts[0].content)


@pytest.mark.parametrize(
    ("status", "reason"), [(401, "provider_refused"), (429, "provider_refused"), (500, "error")]
)
async def test_provider_status(status: int, reason: str) -> None:
    model, _ = _model([ModelHTTPError(status, "m", {"error": "secret body"})])
    outcome = await run_loop(wrap_model(model), _start(), "be brief", Host(), max_steps=3)
    assert (outcome.reason, outcome.detail) == (reason, f"status {status}")


async def test_other_failures_name_only_their_class() -> None:
    model, _ = _model([RuntimeError("provider said something secret")])
    outcome = await run_loop(wrap_model(model), _start(), "be brief", Host(), max_steps=3)
    assert (outcome.reason, outcome.detail) == ("error", "RuntimeError")


async def test_an_empty_answer_is_an_error() -> None:
    model, _ = _model([ModelResponse(parts=[TextPart("  ")])])
    outcome = await run_loop(wrap_model(model), _start(), "be brief", Host(), max_steps=3)
    assert (outcome.reason, outcome.detail) == ("error", "empty answer")


async def test_the_deadline_cuts_a_call_in_flight() -> None:
    async def slow(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        await asyncio.sleep(30)
        return ModelResponse(parts=[TextPart("late")])

    host = Host()
    host.left = 0.05
    outcome = await run_loop(wrap_model(FunctionModel(slow)), _start(), "x", host, max_steps=3)
    assert outcome.reason == "deadline"


async def test_no_time_left_sends_nothing() -> None:
    model, seen = _model([ModelResponse(parts=[TextPart("x")])])
    host = Host()
    host.left = 0
    outcome = await run_loop(wrap_model(model), _start(), "x", host, max_steps=3)
    assert outcome.reason == "deadline" and seen == []


async def test_without_tools_the_model_gets_none() -> None:
    offered: list[int] = []

    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        offered.append(len(info.function_tools))
        return ModelResponse(parts=[TextPart("ok")])

    model = wrap_model(FunctionModel(answer))
    await run_loop(model, _start(), "x", Host(), max_steps=3, use_tools=False)
    await run_loop(model, _start(), "x", Host(), max_steps=3)
    assert offered == [0, 3]


def test_history_keeps_the_newest_turn_and_drops_old_ones_whole() -> None:
    turns = [context.Turn("person", "a" * 10), context.Turn("agent", "b" * 10)]
    turns.append(context.Turn("person", "c" * 30))
    assert [t.text[0] for t in context.window(turns, max_chars=45)] == ["b", "c"]
    assert [t.text[0] for t in context.window(turns, max_chars=5)] == ["c"]
    messages = context.history(turns, "rules")
    assert isinstance(messages[1], ModelResponse)
    assert isinstance(messages[2], ModelRequest)
    assert isinstance(messages[2].parts[0], UserPromptPart)
