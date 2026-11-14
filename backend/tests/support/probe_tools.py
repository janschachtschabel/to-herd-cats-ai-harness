"""Tools for tests only, never in the production catalog (plan M6 task 1):

- `probe_write` writes an effect (an audit entry `test.probe` with its label) in the
  tool's step transaction, the way a writing tool of Tasks 6 and 7 will through the
  services. With `HERD_PROBE_HANG=in-tool` (a child process to be killed) it says
  `in-tool` on stdout after the effect is written, not committed, and waits there.
- `probe_wait` makes the run wait for a person (`Wait`, 72 hours) until its run is in
  `ANSWERED`; then it answers.
- `probe_lock` waits for the advisory lock named by its label (a test holds it from
  another connection), as a tool waits on a page's or a tree's lock.
- `probe_sleep` takes long: `db:<seconds>` in one statement, `loop:<seconds>` outside
  the database.
- `probe_conflict` writes a probe effect, then fails as a deadlock's victim (SQLSTATE
  40P01): with label `once` on its run's first call only, with `always` every time;
  `CONFLICTS` counts the calls per run.

`installed(monkeypatch)` lists them in the catalog for one test; `install()` for a
whole process (the child of the crash test).
"""

import asyncio
import os
import sys
import uuid
from datetime import timedelta

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.agents.toolbox.base import ToolContext, ToolSpec, Wait
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.audit.models import AuditLog
from app.modules.audit.recorder import record
from app.runtime.loop import ToolResult

PROBE_ACTION = "test.probe"
WAIT_HOURS = 72
ANSWERED: set[uuid.UUID] = set()
CONFLICTS: dict[uuid.UUID, int] = {}


class ProbeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str


async def probe_write(ctx: ToolContext, args: ProbeArgs) -> ToolResult:
    await record(ctx.session, ctx.actor, PROBE_ACTION, "run", ctx.run.id, {"label": args.label})
    if os.environ.get("HERD_PROBE_HANG") == "in-tool":
        await ctx.session.flush()
        sys.stdout.write("in-tool\n")
        sys.stdout.flush()
        await asyncio.sleep(3600)
    return ToolResult("probe", f"wrote {args.label}")


async def probe_wait(ctx: ToolContext, args: ProbeArgs) -> ToolResult | Wait:
    if ctx.run.id in ANSWERED:
        return ToolResult("probe", f"answered {args.label}")
    return Wait(utcnow() + timedelta(hours=WAIT_HOURS))


async def probe_lock(ctx: ToolContext, args: ProbeArgs) -> ToolResult:
    await ctx.session.execute(select(func.pg_advisory_xact_lock(func.hashtext(args.label))))
    return ToolResult("probe", f"locked {args.label}")


async def probe_sleep(ctx: ToolContext, args: ProbeArgs) -> ToolResult:
    where, seconds = args.label.split(":")
    if where == "db":
        await ctx.session.execute(select(func.pg_sleep(float(seconds))))
    else:
        await asyncio.sleep(float(seconds))
    return ToolResult("probe", f"slept {args.label}")


async def probe_conflict(ctx: ToolContext, args: ProbeArgs) -> ToolResult:
    CONFLICTS[ctx.run.id] = CONFLICTS.get(ctx.run.id, 0) + 1
    await record(ctx.session, ctx.actor, PROBE_ACTION, "run", ctx.run.id, {"label": args.label})
    if args.label == "always" or CONFLICTS[ctx.run.id] == 1:
        raise_deadlock = "DO $$ BEGIN RAISE EXCEPTION 'probe' USING ERRCODE = '40P01'; END $$"
        await ctx.session.execute(text(raise_deadlock))
    return ToolResult("probe", f"wrote {args.label}")


PROBES = (
    ToolSpec("probe_write", "Write a probe (tests only).", ProbeArgs, probe_write),
    ToolSpec("probe_wait", "Wait for an answer (tests only).", ProbeArgs, probe_wait),
    ToolSpec("probe_lock", "Wait for a lock (tests only).", ProbeArgs, probe_lock),
    ToolSpec("probe_sleep", "Take long (tests only).", ProbeArgs, probe_sleep),
    ToolSpec("probe_conflict", "Lose a deadlock (tests only).", ProbeArgs, probe_conflict),
)


def install() -> None:
    for spec in PROBES:
        CATALOG[spec.name] = spec


def installed(monkeypatch: pytest.MonkeyPatch) -> None:
    for spec in PROBES:
        monkeypatch.setitem(CATALOG, spec.name, spec)


async def effects(session: AsyncSession, run_id: object = None) -> list[str]:
    """The labels `probe_write` committed (of one run, or all), oldest first."""
    stmt = select(AuditLog.details["label"].astext).where(AuditLog.action == PROBE_ACTION)
    if run_id is not None:
        stmt = stmt.where(AuditLog.target_id == run_id)
    return list((await session.scalars(stmt.order_by(AuditLog.created_at))).all())


async def count(session: AsyncSession, model: object, *where: object) -> int:
    stmt = select(func.count()).select_from(model).where(*where)  # type: ignore[arg-type]
    return int(await session.scalar(stmt) or 0)
