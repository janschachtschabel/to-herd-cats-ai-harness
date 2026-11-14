"""The step loop of a run (spec 8.3; plan M5 task 6, M6 decision 1).

Our code, not the model, decides every step: before each model call the host checks
the policy of everything read so far, the rights and the limits, and records the call
afterwards (`StepHost`); before each tool call the host checks the rights again and
runs the tool through the services. The loop sends a request only after the host said
yes, and only with what the host gave it. Each call is one `pydantic_ai.direct.
model_request`, so nothing runs inside the library between our checks.

Stops: `completed` (an answer without tool calls, or a final tool result),
`max_steps` (that many model calls without an answer), `no_progress` (the third
identical tool call), `provider_refused` (401, 402, 403, 429), `error` (anything
else the provider or the network does, an answer that is no use, or a tool the model
invented three times in a row), and what the host decides (`deadline`,
`rights_revoked`, `policy_blocked`, and `error` when a step cannot be recorded or a
tool fails: at once, never a blind retry). The deadline also cuts a call in flight.
The model's text and arguments come without what the database cannot store
(`storable`).

Replay (plan M6 decision 1): a run taken up again passes its journal, the steps it
has recorded. The loop goes through them again without calling the provider or the
host: each recorded answer stands for its model call, each recorded tool result for
its tool call. A recorded tool call without a recorded result (the worker died before
it finished) is run now, through the host, like a new one. After the last recorded
step the loop goes on as usual, with the full history.
"""

import asyncio
import re
import time
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic_ai.direct import model_request
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import ModelRequestParameters

from app.runtime import tools
from app.runtime.models import BuiltModel
from app.runtime.untrusted import frame_untrusted

# What Postgres cannot store in text or JSONB: NUL and lone UTF-16 surrogates.
UNSTORABLE = re.compile("[\x00\ud800-\udfff]")
REFUSED_STATUSES = frozenset({401, 402, 403, 429})
MAX_BAD_CALLS = 3
SAME_CALL_LIMIT = 3  # the third identical call stops the run

Stop = Literal[
    "completed",
    "max_steps",
    "deadline",
    "no_progress",
    "rights_revoked",
    "policy_blocked",
    "provider_refused",
    "error",
    "cancelled",
]


class Halt(Exception):  # noqa: N818 (a decision, raised by the host)
    def __init__(self, reason: Stop, detail: str | None = None) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Reply:
    """One model call as the host records it."""

    text: str
    tool_calls: list[ToolCall]
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    duration_ms: int
    model: str | None


@dataclass(frozen=True, slots=True)
class ToolResult:
    """`text` for the model (framed and cut by the loop); `source` names it; `spaces`:
    where the text came from (the host's record, never sent). A `final` result ends
    the run: its text is the answer, and no call after it runs (`submit_result`)."""

    source: str
    text: str
    attrs: dict[str, str] = field(default_factory=dict)
    spaces: frozenset[uuid.UUID] = frozenset()
    final: bool = False


@dataclass(frozen=True, slots=True)
class Recorded:
    """One step of a run's journal: the model's answer and the results of its tool
    calls that were recorded, by call id."""

    text: str
    tool_calls: tuple[ToolCall, ...]
    results: Mapping[str, ToolResult] = field(default_factory=dict)


class StepHost(Protocol):
    def seconds_left(self) -> float: ...

    async def before_model_call(self, step: int) -> None:
        """Raise `Halt` to stop before anything is sent."""
        ...

    async def after_model_call(self, step: int, reply: Reply) -> None: ...

    async def call_tool(self, step: int, call: ToolCall, args: Any) -> ToolResult:
        """Raise `Halt` to stop instead of running it."""
        ...


@dataclass(frozen=True, slots=True)
class Outcome:
    reason: Stop
    answer: str | None = None
    detail: str | None = None  # for the run's event: a status code or an error class


async def run_loop(
    built: BuiltModel,
    messages: Sequence[ModelMessage],
    instructions: str,
    host: StepHost,
    *,
    max_steps: int,
    offered: Sequence[tools.ToolSchema] = (),
    journal: Sequence[Recorded] = (),
) -> Outcome:
    history = list(messages)
    by_name = {tool.name: tool for tool in offered}
    params = ModelRequestParameters(function_tools=tools.definitions(offered))
    seen: Counter[str] = Counter()
    bad_calls = 0
    for step in range(1, max_steps + 1):
        recorded = journal[step - 1] if step <= len(journal) else None
        if recorded is not None:
            message: ModelResponse = _replayed(recorded)
            text, calls, results = recorded.text, recorded.tool_calls, recorded.results
        else:
            try:
                await host.before_model_call(step)
                response = await _request(built, history, params, host)
            except Halt as halt:
                return Outcome(halt.reason, detail=halt.detail)
            except ModelHTTPError as exc:
                refused = exc.status_code in REFUSED_STATUSES
                reason: Stop = "provider_refused" if refused else "error"
                return Outcome(reason, detail=f"status {exc.status_code}")
            except TimeoutError:
                return Outcome("deadline")
            except Exception as exc:  # the provider or the network; never its text
                return Outcome("error", detail=type(exc).__name__)
            try:
                await host.after_model_call(step, response.reply)
            except Halt as halt:
                return Outcome(halt.reason, detail=halt.detail)
            message, text = response.message, response.reply.text
            calls, results = tuple(response.reply.tool_calls), {}
        history.append(message)
        if not calls:
            if not text.strip():
                return Outcome("error", detail="empty answer")
            return Outcome("completed", answer=text)
        returns: list[ToolReturnPart] = []
        for call in calls:
            try:
                args = tools.parse(by_name, call.name, call.args)
            except tools.BadToolCall as bad:
                bad_calls += 1
                if bad_calls >= MAX_BAD_CALLS:
                    return Outcome("error", detail="bad tool calls")
                returns.append(ToolReturnPart(call.name, str(bad), tool_call_id=call.id))
                continue
            seen[tools.signature(call.name, args)] += 1
            if seen[tools.signature(call.name, args)] >= SAME_CALL_LIMIT:
                return Outcome("no_progress")
            result = results.get(call.id)
            if result is None:
                try:
                    result = await host.call_tool(step, call, args)
                except Halt as halt:
                    return Outcome(halt.reason, detail=halt.detail)
            if result.final:
                return Outcome("completed", answer=result.text)
            framed = frame_untrusted(result.source, result.text, **result.attrs)
            returns.append(ToolReturnPart(call.name, framed, tool_call_id=call.id))
        history.append(ModelRequest(parts=returns, instructions=instructions))
    return Outcome("max_steps")


def _replayed(recorded: Recorded) -> ModelResponse:
    """A recorded answer as the model message it stands for."""
    parts: list[TextPart | ToolCallPart] = [TextPart(recorded.text)] if recorded.text else []
    parts += [ToolCallPart(c.name, c.args, tool_call_id=c.id) for c in recorded.tool_calls]
    return ModelResponse(parts=parts)


@dataclass(frozen=True, slots=True)
class _Response:
    message: ModelResponse
    reply: Reply


async def _request(
    built: BuiltModel,
    history: list[ModelMessage],
    params: ModelRequestParameters,
    host: StepHost,
) -> _Response:
    """One model call, cut at the run's deadline."""
    left = host.seconds_left()
    if left <= 0:
        raise Halt("deadline")
    started = time.monotonic()
    async with asyncio.timeout(left):
        response = await model_request(
            built.model, history, model_settings=built.settings, model_request_parameters=params
        )
    duration_ms = round((time.monotonic() - started) * 1000)
    text = storable("".join(p.content for p in response.parts if isinstance(p, TextPart)))
    calls = [
        ToolCall(p.tool_call_id, p.tool_name, storable(p.args_as_dict()))
        for p in response.parts
        if isinstance(p, ToolCallPart)
    ]
    usage = response.usage
    reply = Reply(
        text=text,
        tool_calls=calls,
        tokens_in=usage.input_tokens,
        tokens_out=usage.output_tokens,
        tokens_cached=min(usage.cache_read_tokens, usage.input_tokens),
        duration_ms=duration_ms,
        model=response.model_name,
    )
    return _Response(response, reply)


def storable[T](value: T) -> T:
    """The model's text and arguments without what the database cannot store (it may
    be asked to write such characters), so a step can always be recorded."""
    if isinstance(value, str):
        return UNSTORABLE.sub("", value)  # type: ignore[return-value]
    if isinstance(value, dict):
        return {storable(k): storable(v) for k, v in value.items()}  # type: ignore[return-value]
    if isinstance(value, list):
        return [storable(v) for v in value]  # type: ignore[return-value]
    return value
