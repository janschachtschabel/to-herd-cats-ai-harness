"""A run's journal as the loop replays it (plan M6 decision 1): its recorded model and
tool calls turned back into steps, what it had read, and where its sequence stands.

The journal is the run's `run_event`s ordered by `seq`, which counts on across
take-ups. Step k is the model call recorded for step k with the tool results recorded
for its calls (by call id). The steps run from 1 without a gap; should one be missing,
the journal ends before it and the loop calls the model again from there.

`renamed` gives recorded calls a tool's name as it is now (an external tool's journal
of an earlier release: `toolbox/external.legacy_names`). A `mark` event restores the
personal mark the run's history gave it (`personal_mark.py`).
"""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from app.modules.agents.actor import Reads
from app.modules.agents.run_models import EventKind, RunEvent
from app.runtime.loop import Recorded, ToolCall, ToolResult


@dataclass(frozen=True, slots=True)
class Replay:
    steps: list[Recorded]
    reads: Reads
    seq: int  # the last `seq` recorded (0 without any)


def replay(events: Iterable[RunEvent]) -> Replay:
    answers: dict[int, Mapping[str, Any]] = {}
    results: dict[int, dict[str, ToolResult]] = {}
    reads = Reads()
    seq = 0
    for event in events:
        seq = max(seq, event.seq)
        content = event.content
        if event.kind == EventKind.MODEL_CALL:
            answers[int(content["step"])] = content
        elif event.kind == EventKind.TOOL_CALL:
            result = _result(content)
            results.setdefault(int(content["step"]), {})[str(content["call_id"])] = result
            read = content.get("read") or {}
            reads.spaces |= result.spaces
            reads.pages |= _ids(read.get("pages"))
            reads.tickets |= _ids(read.get("tickets"))
            reads.drafts |= _ids(read.get("drafts"))
            reads.personal |= read.get("personal") is True
        elif event.kind == EventKind.MARK:  # the history gave it personal content
            reads.personal |= (content.get("read") or {}).get("personal") is True
    steps: list[Recorded] = []
    while (answer := answers.get(len(steps) + 1)) is not None:
        calls = tuple(
            ToolCall(str(c["id"]), str(c["name"]), dict(c.get("args") or {}))
            for c in answer.get("tool_calls") or []
        )
        steps.append(
            Recorded(str(answer.get("text") or ""), calls, results.get(len(steps) + 1, {}))
        )
    return Replay(steps, reads, seq)


def renamed(steps: list[Recorded], names: Mapping[str, str]) -> list[Recorded]:
    """`steps` with each call of an old name under its name now (others as they are)."""
    return [
        replace(
            step,
            tool_calls=tuple(
                replace(call, name=names.get(call.name, call.name)) for call in step.tool_calls
            ),
        )
        for step in steps
    ]


def _result(content: Mapping[str, Any]) -> ToolResult:
    return ToolResult(
        str(content["source"]),
        str(content.get("text") or ""),
        {str(k): str(v) for k, v in (content.get("attrs") or {}).items()},
        frozenset(_ids(content.get("spaces"))),
        final=content.get("final") is True,
    )


def _ids(values: object) -> set[uuid.UUID]:
    if not isinstance(values, list):
        return set()
    return {uuid.UUID(str(value)) for value in values}
