"""A tool call of a run under the personal mark (`personal_mark.py`), for the host
(`step_host.py`).

- `run_tool`: the tool; under the mark a write that owes her release stops before its
  effect (`ReleaseFirst`, its savepoint undone) and asks the person's release of the
  call first; released, it runs again and writes. A call the gate finds to change
  nothing (a preview) runs unreleased, `previewing`: it never writes, and its result
  is the asker's alone (module review M8 3, H1).
- `owes_release`: for a tool on `confirm`, whether its release is the mark's too, so
  its card is personal (says that what is released can be read by others now or
  later, shows it in full, refuses what cannot be shown: `approvals/shown.py`). Under
  the mark every one is, but a message into the run's own conversation alone with her
  (marked itself): decided from the call, never from what the tool would meet now,
  since a refusal when asked (a missing ticket, a right, a draft) can be gone by the
  time she decides (module review M8 5, L2; it replaces M8 4, K5's probe).
"""

from dataclasses import replace
from typing import Any

from app.modules.agents.approvals.gate import Passed, gate
from app.modules.agents.personal_mark import ReleaseFirst
from app.modules.agents.toolbox.base import ToolContext, ToolSpec, Wait
from app.modules.agents.toolbox.message_tools import PostMessageArgs
from app.modules.agents.toolbox.writing import into_own_conversation
from app.runtime.loop import ToolResult


async def owes_release(ctx: ToolContext, args: Any) -> bool:
    if not ctx.reads.personal:
        return False
    if isinstance(args, PostMessageArgs) and ctx.answers_in(args.conversation_id):
        return await into_own_conversation(ctx, args.conversation_id) is not None
    return True


async def run_tool(
    ctx: ToolContext, spec: ToolSpec, args: Any, passed: Passed | None
) -> ToolResult | Wait:
    """The tool; under the personal mark a write that owes her release stops before its
    effect (`ReleaseFirst`, its savepoint undone) and asks the person's release of the
    call first (`personal_mark.py`); released, it runs again and writes. A call the
    gate finds to change nothing (a preview) runs unreleased, `previewing`: it never
    writes, and its result is the asker's alone (module review M8 3, H1)."""
    if passed == Passed.RELEASED or not ctx.reads.personal:
        return await spec.run(replace(ctx, released=passed == Passed.RELEASED), args)
    if passed is None:
        try:
            async with ctx.session.begin_nested():
                return await spec.run(ctx, args)
        except ReleaseFirst:
            held = await gate(ctx, spec, args, personal=True)
            if not isinstance(held, Passed):
                return held
            if held == Passed.RELEASED:
                return await spec.run(replace(ctx, released=True), args)
    return await spec.run(replace(ctx, previewing=True), args)
