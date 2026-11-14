"""The host of a run's step loop (`runtime/loop.StepHost`): the checks before every
model call and every tool call, and the records after them, each in a short
transaction of its own (see `executor.py`, which drives it).

Every step's transaction starts by locking the run's row and checking that it is still
this take-up's (else `Lost`) and that nobody asked it to stop (else `cancelled`). A
tool runs inside its step's transaction, which then records its `run_event`: a tool
that writes commits its effect together with its entry in the journal
(`toolbox/base.py`). A tool that must wait for a person sets the run `waiting` in that
transaction instead, and the host raises `Suspended` once it is committed. A tool the
agent may use only with a person's release (`confirm`) passes `approvals/gate.py`
first, in the same transaction.

Bounds (module review M6, findings 3 and 14):
- A tool's step waits for a lock at most `STEP_LOCK_TIMEOUT_SECONDS` and runs one
  statement at most `STEP_STATEMENT_TIMEOUT_SECONDS` (never past the deadline); a
  step that exceeds them is rolled back, and the model gets `TOOL_TIMED_OUT` as the
  call's result (recorded, so a replay gives it the same).
- The run's deadline cuts a tool call as it cuts a model call (`deadline`): the
  statement bound ends a database wait there, an asyncio timeout a little later
  anything else.
- A step the database rolled back as a deadlock's victim or on a serialization
  failure (`db_errors.is_retryable`) is run once more; a second time it counts as
  any other failure.
- Each step that writes sets the run's lease when it commits (`RunSteps.keep`): the
  worker's renewal passes over a row a step holds."""

import asyncio
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.db_errors import is_timeout
from app.modules.agents.actor import allowed_actor
from app.modules.agents.approvals.gate import gate
from app.modules.agents.control_repository import ControlRepository
from app.modules.agents.executor_repository import RunSteps
from app.modules.agents.models import (
    STEP_LOCK_TIMEOUT_SECONDS,
    STEP_STATEMENT_TIMEOUT_SECONDS,
    Agent,
    EventKind,
    Run,
)
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.repository import AgentRepository
from app.modules.agents.step_records import (
    TIMED_OUT_SOURCE,
    TOOL_TIMED_OUT,
    progress,
    reply_content,
    tool_content,
)
from app.modules.agents.toolbox.base import CallRef, RunRef, ToolContext, ToolSpec, Wait
from app.modules.agents.toolbox.policy import Grant, effective
from app.modules.agents.working import Lost, Suspended, Unit, Working, once_more, units_of
from app.modules.ai.models import DataLocation, UsageRecord
from app.modules.ai.policy import ANY, connection_allowed, strictest
from app.modules.ai.usage import record_usage
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
            steps, _, agent = await self._owned(session)
            await self._actor(session, agent)
            connection = await steps.connection(self.run.connection_id)
            if connection is None:
                raise Halt("rights_revoked")
            await self._policy(session, connection.data_location)
            return await steps.take_rate(connection.id, connection.requests_per_minute)

    async def after_model_call(self, step: int, reply: Reply) -> None:
        try:
            await once_more(self.run, lambda: self._record_reply(step, reply))
        except (Lost, Halt):
            raise
        except Exception as exc:  # the step cannot be recorded: count the call, stop now
            async with self.unit() as session:
                if await RunSteps(session, self.run.claimed).owned() is None:
                    raise Lost from exc
                await self._usage(session, reply)
            raise Halt("error", detail=type(exc).__name__) from exc

    async def _record_reply(self, step: int, reply: Reply) -> None:
        async with self.unit() as session:
            steps, run, _ = await self._owned(session)
            usage = await self._usage(session, reply)
            content = reply_content(step, reply)
            if usage.cost is not None:
                content["cost"] = str(usage.cost)  # the run view shows it per step
            await steps.event(self._seq(), EventKind.MODEL_CALL, content)
            run.steps += 1
            await progress(session, self.run.claimed, run.steps)
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
                result = await once_more(self.run, lambda: self._tool_step(step, call, args, spec))
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
            steps, run, agent = await self._owned(session)
            statement = min(STEP_STATEMENT_TIMEOUT_SECONDS, self.seconds_left())
            await steps.limit_time(STEP_LOCK_TIMEOUT_SECONDS, statement)
            grant = await self._granted(session, agent, spec)
            actor = await self._actor(session, agent)
            location = await self._location(steps)
            reads = self.run.reads
            pages, tickets = set(reads.pages), set(reads.tickets)
            ctx = ToolContext(session, actor, location, reads, self._ref(), CallRef(step, call.id))
            started = time.perf_counter()
            held = await gate(ctx, spec, args) if grant == Grant.CONFIRM else None
            result = held if held is not None else await spec.run(ctx, args)
            duration_ms = round((time.perf_counter() - started) * 1000)
            if isinstance(result, Wait):
                await steps.wait(run, result.until)
                return result
            read = (reads.pages - pages, reads.tickets - tickets)
            content = tool_content(step, call, args, result, duration_ms, read)
            await steps.event(self._seq(), EventKind.TOOL_CALL, content)
            steps.keep(run)
            return result

    async def _timed_out(self, step: int, call: ToolCall, args: Any) -> ToolResult:
        """The call's result is the timeout, recorded like any result."""
        result = ToolResult(TIMED_OUT_SOURCE, TOOL_TIMED_OUT)
        async with self.unit() as session:
            steps, run, _ = await self._owned(session)
            content = tool_content(step, call, args, result, 0)
            await steps.event(self._seq(), EventKind.TOOL_CALL, content)
            steps.keep(run)
        return result

    # --- checks ----------------------------------------------------------------------

    async def _owned(self, session: AsyncSession) -> tuple[RunSteps, Run, Agent]:
        """The run's records, its row (locked) and its agent as now."""
        steps = RunSteps(session, self.run.claimed)
        run = await steps.owned()
        if run is None:
            raise Lost
        if await ControlRepository(session, run.org_id).cancelled_by(run.id) is not None:
            raise Halt("cancelled")
        agent = await steps.agent()
        if agent is None:
            raise Halt("rights_revoked")
        self.run.agent = agent
        return steps, run, agent

    async def _granted(self, session: AsyncSession, agent: Agent, spec: ToolSpec) -> Grant:
        """The tool is still allowed to the agent as it is now (level and entries):
        `allow`, or `confirm` (a person releases each call, `approvals/gate.py`)."""
        entries = await AgentRepository(session, agent.org_id).tool_entries(agent.id)
        entry = Grant(entries[spec.name]) if spec.name in entries else None
        grant = effective(agent.level, spec, entry)
        if grant == Grant.BLOCK:
            raise Halt("rights_revoked")
        return grant

    async def _actor(self, session: AsyncSession, agent: Agent) -> Actor:
        claimed = self.run.claimed
        actor = await allowed_actor(
            session,
            claimed.org_id,
            claimed.user_id,
            agent,
            self.run.reads,
            claimed.conversation_id,
        )
        if actor is None:
            raise Halt("rights_revoked")
        return actor

    async def _policy(self, session: AsyncSession, location: DataLocation) -> None:
        """The strictest current policy of every space read from, where it was read
        and where its page or ticket is now."""
        repo = ReadRepository(session, self.run.claimed.org_id)
        now = await repo.now(self.run.reads)
        policy = strictest([ANY, *await repo.policies(self.run.reads.spaces | now.spaces)])
        if now.blocked or not connection_allowed(location, policy):
            raise Halt("policy_blocked")

    async def _location(self, steps: RunSteps) -> DataLocation:
        connection = await steps.connection(self.run.connection_id)
        if connection is None:
            raise Halt("rights_revoked")
        return DataLocation(connection.data_location)

    async def _usage(self, session: AsyncSession, reply: Reply) -> UsageRecord:
        claimed = self.run.claimed
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
        )

    def _ref(self) -> RunRef:
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

    def _seq(self) -> int:
        self.run.seq += 1
        return self.run.seq
