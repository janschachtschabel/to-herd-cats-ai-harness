"""A tool call of a run under the personal mark (`personal_mark.py`), for the host
(`step_host.py`).

- `run_tool`: the tool; under the mark a write that owes her release stops before its
  effect (`ReleaseFirst`, its savepoint undone) and asks the person's release of the
  call first; released, it runs again and writes. A call the gate finds to change
  nothing (a preview) runs unreleased, `previewing`: it never writes, and its result
  is the asker's alone (module review M8 3, H1).
- `owes_release`: for a tool on `confirm`, whether its release is the mark's too, so
  its card is personal (says that what is released can be read by others now or
  later, shows it in full, refuses what cannot be shown: `approvals/shown.py`) only
  then (module review M8 4, K5). The tool runs `probing` on a copy of what the run
  read, in a savepoint that is always undone: its checks run, `writing.effect` raises
  `ReleaseFirst` where the mark owes the release and never writes.
"""

import copy
from dataclasses import replace
from typing import Any

from app.modules.agents.approvals.gate import Passed, gate
from app.modules.agents.personal_mark import ReleaseFirst
from app.modules.agents.toolbox.base import Owed, ToolContext, ToolSpec, Wait
from app.runtime.loop import ToolResult


class _Undo(Exception):
    """Ends a probe's savepoint, whatever the tool did."""


async def owes_release(ctx: ToolContext, spec: ToolSpec, args: Any) -> bool:
    probe = replace(ctx, probing=True, reads=copy.deepcopy(ctx.reads), owed=Owed())
    try:
        async with ctx.session.begin_nested():
            await spec.run(probe, args)
            raise _Undo
    except ReleaseFirst:
        return True
    except _Undo:
        return False


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
