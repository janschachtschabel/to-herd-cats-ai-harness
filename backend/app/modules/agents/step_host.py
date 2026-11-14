"""The host of a run's step loop (`runtime/loop.StepHost`): the checks before every
model call and every tool call, and the records after them, each in a short
transaction of its own (see `executor.py`, which drives it).

Every step's transaction starts by locking the run's row and checking that it is still
this take-up's (else `Lost`) and that nobody asked it to stop (else `cancelled`). A
tool runs inside its step's transaction, which then records its `run_event`: a tool
that writes commits its effect together with its entry in the journal
(`toolbox/base.py`). A tool that must wait for a person sets the run `waiting` in that
transaction instead, and the host raises `Suspended` once it is committed."""

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.access import Actor
from app.core.outbox import EventActor, emit
from app.core.principal import Principal
from app.modules.agents.actor import Reads, allowed_actor
from app.modules.agents.control_repository import ControlRepository
from app.modules.agents.executor_repository import Claimed, RunSteps
from app.modules.agents.models import Agent, EventKind, Run
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.repository import AgentRepository
from app.modules.agents.toolbox.base import RunRef, ToolContext, ToolSpec, Wait
from app.modules.agents.toolbox.policy import Grant, effective
from app.modules.ai.models import DataLocation
from app.modules.ai.policy import ANY, connection_allowed, strictest
from app.modules.ai.usage import record_usage
from app.runtime.loop import Halt, Reply, ToolCall, ToolResult


class Lost(Exception):  # noqa: N818 (a state: the run is no longer this attempt's)
    pass


class Suspended(Exception):  # noqa: N818 (a state: the run waits for a person)
    pass


@dataclass(slots=True)
class Working:
    """One attempt of a run as the executor works it."""

    claimed: Claimed
    agent: Agent
    connection_id: uuid.UUID
    model: str  # the model the calls go to, as at the start (usage is booked on it)
    secret_ref: str | None
    deadline: float
    reads: Reads = field(default_factory=Reads)
    seq: int = 0  # the last recorded; the journal counts on across take-ups
    tools: list[ToolSpec] = field(default_factory=list)  # allowed at the take-up


Unit = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def units_of(sessions: async_sessionmaker[AsyncSession]) -> Unit:
    """A unit of work per call: a session in a transaction, committed at the end."""

    @asynccontextmanager
    async def unit() -> AsyncIterator[AsyncSession]:
        async with sessions() as session, session.begin():
            yield session

    return unit


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
            async with self.unit() as session:
                steps, _, agent = await self._owned(session)
                await self._actor(session, agent)
                connection = await steps.connection(self.run.connection_id)
                if connection is None:
                    raise Halt("rights_revoked")
                await self._policy(session, connection.data_location)
                wait = await steps.take_rate(connection.id, connection.requests_per_minute)
            if wait <= 0:
                return
            if wait >= self.seconds_left():
                raise Halt("deadline")
            await asyncio.sleep(wait)

    async def after_model_call(self, step: int, reply: Reply) -> None:
        try:
            async with self.unit() as session:
                steps, run, _ = await self._owned(session)
                await steps.event(self._seq(), EventKind.MODEL_CALL, _reply_content(step, reply))
                await self._usage(session, reply)
                run.steps += 1
                await _progress(session, self.run.claimed, run.steps)
        except (Lost, Halt):
            raise
        except Exception as exc:  # the step cannot be recorded: count the call, stop now
            async with self.unit() as session:
                if await RunSteps(session, self.run.claimed).owned() is None:
                    raise Lost from exc
                await self._usage(session, reply)
            raise Halt("error", detail=type(exc).__name__) from exc

    async def call_tool(self, step: int, call: ToolCall, args: Any) -> ToolResult:
        spec = self.tools.get(call.name)
        if spec is None:  # the loop offers and parses only these
            raise Halt("error", detail="unknown tool")
        try:
            async with self.unit() as session:
                steps, run, agent = await self._owned(session)
                await self._granted(session, agent, spec)
                actor = await self._actor(session, agent)
                location = await self._location(steps)
                reads = self.run.reads
                pages, tickets = set(reads.pages), set(reads.tickets)
                ctx = ToolContext(session, actor, location, reads, self._ref())
                result = await spec.run(ctx, args)
                if isinstance(result, Wait):
                    await steps.wait(run, result.until)
                else:
                    content = {
                        "step": step,
                        "call_id": call.id,
                        "name": call.name,
                        "args": args.model_dump(mode="json"),
                        "source": result.source,
                        "attrs": result.attrs,
                        "text": result.text,
                        "spaces": sorted(str(space_id) for space_id in result.spaces),
                        "read": {
                            "pages": sorted(str(p) for p in reads.pages - pages),
                            "tickets": sorted(str(t) for t in reads.tickets - tickets),
                        },
                    }
                    await steps.event(self._seq(), EventKind.TOOL_CALL, content)
        except (Lost, Halt):
            raise
        except Exception as exc:  # a tool that fails ends the run, never retried blind
            raise Halt("error", detail=type(exc).__name__) from exc
        if isinstance(result, Wait):
            raise Suspended
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

    async def _granted(self, session: AsyncSession, agent: Agent, spec: ToolSpec) -> None:
        """The tool is still allowed to the agent as it is now (level and entries)."""
        entries = await AgentRepository(session, agent.org_id).tool_entries(agent.id)
        entry = Grant(entries[spec.name]) if spec.name in entries else None
        if effective(agent.level, spec, entry) != Grant.ALLOW:
            raise Halt("rights_revoked")

    async def _actor(self, session: AsyncSession, agent: Agent) -> Actor:
        claimed = self.run.claimed
        actor = await allowed_actor(session, claimed.org_id, claimed.user_id, agent, self.run.reads)
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

    async def _usage(self, session: AsyncSession, reply: Reply) -> None:
        claimed = self.run.claimed
        await record_usage(
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
        return RunRef(c.id, c.org_id, c.agent_id, c.user_id, c.conversation_id)

    def _seq(self) -> int:
        self.run.seq += 1
        return self.run.seq


async def _progress(session: AsyncSession, claimed: Claimed, steps: int) -> None:
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


def _reply_content(step: int, reply: Reply) -> dict[str, object]:
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
