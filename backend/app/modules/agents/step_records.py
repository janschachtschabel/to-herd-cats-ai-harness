"""What a run's steps record (`step_host.py`): the content of a model call's and a tool
call's `run_event` (replayed by `journal.py`), and the `run.progress` event."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventActor, emit
from app.core.principal import Principal
from app.modules.agents.actor import Reads
from app.modules.agents.executor_repository import Claimed
from app.runtime.loop import Reply, ToolCall, ToolResult

# A tool's step that waited for a lock or ran a statement longer than its bound
# (`step_host`): what the model is told instead of the tool's result.
TOOL_TIMED_OUT = (
    "tool_timeout: the tool waited too long for data another task is changing, or took "
    "too long; nothing it did was kept. Try again later, or go on without it."
)
TIMED_OUT_SOURCE = "host"


async def progress(session: AsyncSession, claimed: Claimed, steps: int) -> None:
    """`run.progress` for the DM's person (ids and the step counter only)."""
    await emit(
        session,
        type="run.progress",
        actor=EventActor(claimed.org_id, Principal.agent(claimed.agent_id)),
        space_id=None,
        subject_type="run",
        subject_id=claimed.id,
        payload={
            "conversation_id": str(claimed.conversation_id),
            "run_id": str(claimed.id),
            "step": steps,
        },
    )


def reply_content(step: int, reply: Reply) -> dict[str, object]:
    return {
        "step": step,
        "text": reply.text,
        "tool_calls": [{"id": c.id, "name": c.name, "args": c.args} for c in reply.tool_calls],
        "tokens_in": reply.tokens_in,
        "tokens_out": reply.tokens_out,
        "tokens_cached": reply.tokens_cached,
        "duration_ms": reply.duration_ms,
        "model": reply.model,
    }


def tool_content(
    step: int,
    call: ToolCall,
    args: Any,
    result: ToolResult,
    duration_ms: int,
    read: tuple[set[uuid.UUID], set[uuid.UUID], set[uuid.UUID]] = (set(), set(), set()),
) -> dict[str, object]:
    """`read`: the pages, tickets and drafts' spaces the call read (new to the run)."""
    content: dict[str, object] = {
        "step": step,
        "call_id": call.id,
        "name": call.name,
        "args": args.model_dump(mode="json"),
        "source": result.source,
        "attrs": result.attrs,
        "text": result.text,
        "spaces": sorted(str(space_id) for space_id in result.spaces),
        "duration_ms": duration_ms,
        "read": {
            "pages": sorted(str(p) for p in read[0]),
            "tickets": sorted(str(t) for t in read[1]),
            "drafts": sorted(str(d) for d in read[2]),
        },
    }
    if result.final:
        content["final"] = True
    return content


Snapshot = tuple[set[uuid.UUID], set[uuid.UUID], set[uuid.UUID], set[uuid.UUID]]


def snapshot(reads: Reads) -> Snapshot:
    return set(reads.spaces), set(reads.pages), set(reads.tickets), set(reads.drafts)


def restore(reads: Reads, saved: Snapshot) -> None:
    """What the run had read before a step that was rolled back (in place: the step's
    tool context shares the object)."""
    sets = (reads.spaces, reads.pages, reads.tickets, reads.drafts)
    for now, then in zip(sets, saved, strict=True):
        now.clear()
        now.update(then)
