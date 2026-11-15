"""The host of a run's step loop (`runtime/loop.StepHost`): the checks before every
model call and every tool call, and the records after them, each in a short
transaction of its own (see `executor.py`, which drives it; the checks themselves:
`step_checks.py`).

Every step's transaction starts by locking the run's row and checking that it is still
this take-up's (else `Lost`) and that nobody asked it to stop (else `cancelled`). A
tool runs inside its step's transaction, which then records its `run_event`: a tool
that writes commits its effect together with its entry in the journal
(`toolbox/base.py`). A tool that must wait for a person sets the run `waiting` in that
transaction instead, and the host raises `Suspended` once it is committed. A tool the
agent may use only with a person's release (`confirm`) passes `approvals/gate.py`
first, in the same transaction; under the personal mark a write others could read
asks that release too (`_run`, `personal_mark.py`), whatever the grant. An external
MCP server's tool (`ToolSpec.remote`) runs in two transactions around the remote call
instead (`external_step.py`).

Bounds (module review M6, findings 3 and 14; review 2, finding 8):
- Every step (the checks before a model call, the record after it, a tool's step,
  from its first statement, the run's row lock included) waits for a lock at most
  `STEP_LOCK_TIMEOUT_SECONDS` and runs one statement at most
  `STEP_STATEMENT_TIMEOUT_SECONDS` (a tool's step never past the deadline). A tool's
  step that exceeds them is rolled back, and the model gets `TOOL_TIMED_OUT` as the
  call's result (recorded, so a replay gives it the same); the checks before a model
  call end the run `error`, a record that cannot be written too (its usage counted).
- The run's deadline cuts a tool call as it cuts a model call (`deadline`): the
  statement bound ends a database wait there, an asyncio timeout a little later
  anything else.
- A step the database rolled back as a deadlock's victim or on a serialization
  failure (`db_errors.is_retryable`) is run once more; a second time it counts as
  any other failure.
- Each step that writes sets the run's lease when it commits (`RunSteps.keep`): the
  worker's renewal passes over a row a step holds.
- A daily budget reached (`ai/budgets.py`) ends the run with `budget` before the next
  model call (summed before the run's row lock; the other checks come first); a call
  already sent is never cut (plan M7 decision 10)."""

import asyncio
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db_errors import is_timeout
from app.core.outbox import caused_by
from app.modules.agents.approvals.gate import gate, settle_timed_out
from app.modules.agents.executor_repository import RunSteps
from app.modules.agents.external_step import call_external
from app.modules.agents.personal_step import owes_release, run_tool
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.run_models import (
    STEP_LOCK_TIMEOUT_SECONDS,
    STEP_STATEMENT_TIMEOUT_SECONDS,
    EventKind,
)
from app.modules.agents.step_checks import (
    check_policy,
    exhausted,
    granted,
    location_of,
    owned,
    run_actor_now,
)
from app.modules.agents.step_records import (
    TIMED_OUT_SOURCE,
    TOOL_TIMED_OUT,
    progress,
    reply_content,
    tool_content,
)
from app.modules.agents.toolbox.base import CallRef, RunRef, ToolContext, ToolSpec, Wait
from app.modules.agents.toolbox.policy import Grant
from app.modules.agents.working import Lost, Suspended, Unit, Working, once_more, units_of
from app.modules.ai.models import UsageRecord
from app.modules.ai.usage import record_usage
from app.modules.automations import runs as automation_runs
from app.runtime.loop import Halt, Reply, ToolCall, ToolResult

CUT_GRACE_SECONDS = 1.0  # past the deadline, an asyncio timeout ends what the database did not
__all__ = ["TOOL_TIMED_OUT", "Lost", "RunHost", "Suspended", "Unit", "Working", "units_of"]


class RunHost:
    """The run's `StepHost`; what it checks and records: `executor.py`."""

    def __init__(self, unit: Unit, clock: Callable[[], float], run: Working) -> None:
        self.unit = unit
        self.clock = clock
        self.run = run
        self.tools = {tool.name: tool for tool in run.tools}

    def seconds_left(self) -> float:
        return self.run.deadline - self.clock()

    async def before_model_call(self, step: int) -> None:
        while True:
            wait = await once_more(self.run, self._admit)
            if wait <= 0:
                return
            if wait >= self.seconds_left():
                raise Halt("deadline")
            await asyncio.sleep(wait)

    async def _admit(self) -> float:
        """The checks before a model call, and a place in the rate window (0.0)."""
        async with self.unit() as session:
            steps = RunSteps(session, self.run.claimed)
            await steps.limit_time(STEP_LOCK_TIMEOUT_SECONDS, STEP_STATEMENT_TIMEOUT_SECONDS)
            connection = await steps.connection(self.run.connection_id)
            spent = await exhausted(session, self.run, connection)  # before the row lock
            steps, _, agent = await owned(session, self.run)
            await run_actor_now(session, self.run, agent)
            if connection is None:
                raise Halt("rights_revoked")
            await check_policy(session, self.run, connection.data_location)
            if spent is not None:
                raise Halt("budget", detail=spent.value)
            return await steps.take_rate(connection.id, connection.requests_per_minute)

    async def after_model_call(self, step: int, reply: Reply) -> None:
        try:
            await once_more(self.run, lambda: self._record_reply(step, reply))
        except (Lost, Halt):
            raise
        except Exception as exc:  # the step cannot be recorded: count the call, stop now
            async with self.unit() as session:
                steps = RunSteps(session, self.run.claimed)
                await steps.limit_time(STEP_LOCK_TIMEOUT_SECONDS, STEP_STATEMENT_TIMEOUT_SECONDS)
                if await steps.owned() is None:
                    raise Lost from exc
                await self._usage(session, reply)
            raise Halt("error", detail=type(exc).__name__) from exc

    async def _record_reply(self, step: int, reply: Reply) -> None:
        async with self.unit() as session:
            steps, run, _ = await owned(session, self.run)
            usage = await self._usage(session, reply)
            content = reply_content(step, reply)
            if usage.cost is not None:
                content["cost"] = str(usage.cost)  # the run view shows it per step
            await steps.event(self.next_seq(), EventKind.MODEL_CALL, content)
            run.steps += 1
            claimed = self.run.claimed
            in_place = claimed.automation_id is None or await automation_runs.heard_in_place(
                session, claimed.org_id, claimed.id
            )
            await progress(session, claimed, run.steps, in_place=in_place)
            steps.keep(run)

    async def call_tool(self, step: int, call: ToolCall, args: Any) -> ToolResult:
        spec = self.tools.get(call.name)
        if spec is None:  # the loop offers and parses only these
            raise Halt("error", detail="unknown tool")
        left = self.seconds_left()
        if left <= 0:
            raise Halt("deadline")
        try:
            async with asyncio.timeout(left + CUT_GRACE_SECONDS):
                result = await (
                    call_external(self, step, call, args, spec)
                    if spec.remote is not None
                    else once_more(self.run, lambda: self._tool_step(step, call, args, spec))
                )
        except (Lost, Halt):
            raise
        except TimeoutError as exc:  # anything but the database, past the deadline
            raise Halt("deadline") from exc
        except Exception as exc:  # a tool that fails ends the run, never retried blind
            if not is_timeout(exc):
                raise Halt("error", detail=type(exc).__name__) from exc
            if self.seconds_left() <= 0:
                raise Halt("deadline") from exc
            result = await once_more(self.run, lambda: self._timed_out(step, call, args))
        if isinstance(result, Wait):
            raise Suspended
        return result

    async def _tool_step(
        self, step: int, call: ToolCall, args: Any, spec: ToolSpec
    ) -> ToolResult | Wait:
        async with self.unit() as session:
            statement = min(STEP_STATEMENT_TIMEOUT_SECONDS, self.seconds_left())
            steps, run, agent = await owned(session, self.run, statement)
            grant = await granted(session, self.run, agent, spec)
            actor = await run_actor_now(session, self.run, agent)
            location = await location_of(steps, self.run)
            reads = self.run.reads
            pages, tickets, drafts = set(reads.pages), set(reads.tickets), set(reads.drafts)
            marked = reads.personal
            ctx = ToolContext(session, actor, location, reads, self.ref(), CallRef(step, call.id))
            started = time.perf_counter()
            with caused_by(run.id):  # what the tool emits names the run (plan M7)
                held = None
                if grant == Grant.CONFIRM:  # personal: only if the mark owes it (K5)
                    personal = marked and await owes_release(ctx, spec, args)
                    held = await gate(ctx, spec, args, personal=personal)
                if isinstance(held, ToolResult | Wait):
                    result: ToolResult | Wait = held
                else:  # a release covers the mark too
                    result = await run_tool(ctx, spec, args, held)
            duration_ms = round((time.perf_counter() - started) * 1000)
            if isinstance(result, Wait):
                await steps.wait(run, result.until)
                return result
            repo = ReadRepository(session, run.org_id)
            reads.drafts |= await repo.draft_spaces(reads.pages - pages)  # as read
            read = (reads.pages - pages, reads.tickets - tickets, reads.drafts - drafts)
            # a tool that handed the run personal content marks it, journaled with it
            personal = reads.personal and not marked
            content = tool_content(step, call, args, result, duration_ms, read, personal=personal)
            await steps.event(self.next_seq(), EventKind.TOOL_CALL, content)
            steps.keep(run)
            return result

    async def _timed_out(self, step: int, call: ToolCall, args: Any) -> ToolResult:
        """The call's result is the timeout, recorded like any result (a released call:
        its approval `failed`)."""
        result = ToolResult(TIMED_OUT_SOURCE, TOOL_TIMED_OUT)
        async with self.unit() as session:
            steps, run, _ = await owned(session, self.run)
            await settle_timed_out(session, self.ref(), CallRef(step, call.id))
            content = tool_content(step, call, args, result, 0)
            await steps.event(self.next_seq(), EventKind.TOOL_CALL, content)
            steps.keep(run)
        return result

    async def _usage(self, session: AsyncSession, reply: Reply) -> UsageRecord:
        """Booked to the person, the agent and the space of the place (none for a DM)."""
        claimed = self.run.claimed
        place = await RunSteps(session, claimed).conversation()
        return await record_usage(
            session,
            org_id=claimed.org_id,
            connection_id=self.run.connection_id,
            model=self.run.model,
            tokens_in=reply.tokens_in,
            tokens_out=reply.tokens_out,
            tokens_cached=reply.tokens_cached,
            duration_ms=reply.duration_ms,
            user_id=claimed.user_id,
            agent_id=claimed.agent_id,
            run_id=claimed.id,
            space_id=place.space_id,
        )

    def ref(self) -> RunRef:
        c = self.run.claimed
        return RunRef(
            c.id,
            c.org_id,
            c.agent_id,
            c.user_id,
            c.conversation_id,
            self.run.reply_to,
            c.chain_depth,
        )

    def next_seq(self) -> int:
        self.run.seq += 1
        return self.run.seq
