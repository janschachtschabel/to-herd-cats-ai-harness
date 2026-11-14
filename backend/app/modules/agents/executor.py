"""One run, from its claim to its answer (plan M5 task 6; spec 8.3).

The step loop is `runtime/loop.py`; this is its host (`StepHost`): our code decides
every step, in short transactions of its own, none of them open while the provider
works.

- Before every model call: the run is still this attempt's; the person still acts and
  has `ai.use`, the agent may run, and every space read so far, where it was read and
  where its page or ticket is now, is still visible to the person and the agent
  together (`actor.allowed_actor`; else `rights_revoked`); the current policies of
  those spaces, with the conversation as `any`, allow the connection's data location
  now, and no page read has been locked for AI, trashed or deleted since, nor a ticket
  deleted (else `policy_blocked`); then a place in the connection's
  `requests_per_minute`.
- After every model call, in one transaction: the step's `run_event`, its usage
  (`record_usage`) and the step counter. The event's key (run, attempt, step) is
  unique and the transaction checks the attempt first, so a call is recorded once,
  whatever worker died when.
- Every tool call: the rights again, the tool through the services with the run's
  actor (`tools.py`), and its `run_event` with the full result. A step that cannot be
  recorded, or a tool that fails, ends the run with `error` at once (the call's usage
  is still recorded).
- The end, in one transaction (`close`): the answer (`kind=agent`, `client_id` = the
  run, so there is never a second one), or on any other stop a timeline notice in the
  DM (`run.stopped` with the reason, for the client to word); the run `done`. A cancel
  request found there wins over any other end (`cancelled`, no answer). A message the
  person sent after the run started that no queued run will answer (it came while the
  run waited) gets a run of its own, queued in the same transaction. A run whose
  question was deleted before it started (no person's message after the last answer)
  ends `completed` at once, without a call, an answer or a notice.

Taking a run up again (plan M6 decision 1): the run replays its journal (`journal.py`)
and goes on after its last recorded step, with what it had read restored; the
conversation it answers ends at its first start. A run that waits (a tool answered
`Wait`) ends this take-up without an end (`execute` gives None).

A worker that lost the run (its lease ran out and another worker took it) notices at
its next write and stops without writing anything (`Lost`). The provider's key is
resolved only now, for this take-up's client, and never stored or logged.
"""

import json
import time
from collections.abc import Callable
from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.models_base import utcnow
from app.core.outbox import EventActor, emit
from app.core.principal import Principal
from app.modules.agents.actor import allowed_actor, run_actor
from app.modules.agents.control_repository import ControlRepository
from app.modules.agents.executor_repository import Claimed, RunSteps
from app.modules.agents.journal import replay
from app.modules.agents.models import EventKind, Run, StopReason
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.repository import AgentRepository
from app.modules.agents.run_repository import RunRepository
from app.modules.agents.standing import refusal
from app.modules.agents.step_host import Lost, RunHost, Suspended, Unit, Working
from app.modules.agents.toolbox.catalog import offered
from app.modules.agents.toolbox.policy import Grant, allowed
from app.modules.ai.models import AiConnection, ConnectionKind, ParamFamily
from app.modules.ai.provider import egress_proxy, rules_for
from app.modules.messaging.models import MAX_BODY_CHARS, Message
from app.modules.messaging.thread_repository import ThreadRepository
from app.runtime import context, models
from app.runtime.loop import Outcome, Recorded, run_loop

MAX_RECOVERIES = 2  # a run taken up again this often after its worker died: `error`
STOP_KEY = "run.stopped"
STOP_SEQ = 0  # the stop's event; the steps' events count from 1

ModelMaker = Callable[[models.ModelTarget, float], models.BuiltModel]


class Executor:
    def __init__(
        self,
        unit: Unit,
        *,
        make_model: ModelMaker = models.make_model,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.unit = unit
        self.make_model = make_model
        self.clock = clock

    async def execute(self, claimed: Claimed) -> StopReason | None:
        """Work the run to its end; its stop reason, or None if it was lost or now
        waits."""
        try:
            prepared = await self._prepare(claimed)
            if isinstance(prepared, Outcome):
                return await self._finish(claimed, prepared)
            outcome = await self._loop(*prepared)
            return await self._finish(claimed, outcome)
        except (Lost, Suspended):
            return None

    async def _prepare(
        self, claimed: Claimed
    ) -> Outcome | tuple[Working, models.ModelTarget, context.Messages, str, list[Recorded]]:
        async with self.unit() as session:
            steps = RunSteps(session, claimed)
            if await steps.owned() is None:
                raise Lost
            if await ControlRepository(session, claimed.org_id).cancelled_by(claimed.id):
                return Outcome("cancelled")
            agent = await steps.agent()
            if agent is None:
                return Outcome("rights_revoked")
            if claimed.recoveries > MAX_RECOVERIES:
                return Outcome("error", detail="attempts")
            org, user = claimed.org_id, claimed.user_id
            journal = replay(await steps.journal())
            if await allowed_actor(session, org, user, agent, journal.reads) is None:
                return Outcome("rights_revoked")
            connection = await steps.connection(agent.connection_id)
            assert connection is not None  # agent_refusal checked it
            said = await ReadRepository(session, org).said(
                claimed.conversation_id, claimed.started_at
            )
            if not said or said[-1].by_agent:  # its question was deleted: nothing to answer
                return Outcome("completed")
            target = _target(connection, agent.model)
            deadline = self.clock() + agent.max_runtime_seconds
            entries = await AgentRepository(session, org).tool_entries(agent.id)
            grants = {name: Grant(policy) for name, policy in entries.items()}
            tools = allowed(agent.level, offered(), grants) if target.supports_tools else []
            run = Working(
                claimed,
                agent,
                connection.id,
                target.model,
                connection.secret_ref,
                deadline,
                reads=journal.reads,
                seq=journal.seq,
                tools=tools,
            )
        turns = [context.Turn("agent" if s.by_agent else "person", s.text) for s in said]
        instructions = context.instructions(agent.name, agent.instructions)
        history = context.history(turns, instructions)
        return run, target, history, instructions, journal.steps

    async def _loop(
        self,
        run: Working,
        target: models.ModelTarget,
        messages: context.Messages,
        instructions: str,
        journal: list[Recorded],
    ) -> Outcome:
        try:
            key = secrets.resolve(run.secret_ref) if run.secret_ref else None
        except secrets.SecretUnavailable:
            return Outcome("error", detail="secret unavailable")
        timeout = max(run.deadline - self.clock(), 1.0)
        built = self.make_model(replace(target, api_key=key), timeout)
        host = RunHost(self.unit, self.clock, run)
        try:
            return await run_loop(
                built,
                messages,
                instructions,
                host,
                max_steps=run.agent.max_steps,
                offered=run.tools,
                journal=journal,
            )
        finally:
            await built.close()

    async def _finish(self, claimed: Claimed, outcome: Outcome) -> StopReason:
        async with self.unit() as session:
            steps = RunSteps(session, claimed)
            run = await steps.owned()
            if run is None:
                raise Lost
            return await close(
                session, steps, run, StopReason(outcome.reason), outcome.answer, outcome.detail
            )


async def close(
    session: AsyncSession,
    steps: RunSteps,
    run: Run,
    reason: StopReason,
    answer: str | None = None,
    detail: str | None = None,
) -> StopReason:
    """End the run (locked by the caller) with its answer or a notice, and queue the
    run for a question it leaves unanswered."""
    claimed = steps.run
    by = await ControlRepository(session, claimed.org_id).cancelled_by(run.id)
    if by is not None:
        reason, answer, detail = StopReason.CANCELLED, None, None
    acting = EventActor(claimed.org_id, Principal.agent(claimed.agent_id))
    message: Message | None = None
    system = False
    if reason == StopReason.COMPLETED:
        if answer is not None:
            message = await steps.answer(answer[:MAX_BODY_CHARS])
    else:
        body = json.dumps({"key": STOP_KEY, "to": reason.value})
        notice = ThreadRepository(session, claimed.org_id)
        conversation = await steps.conversation()
        message = await notice.add_system(conversation, claimed.id, body, utcnow())
        system = True
    if message is not None:
        payload: dict[str, object] = {
            "conversation_id": str(claimed.conversation_id),
            "message_id": str(message.id),
            "parent_id": None,
        }
        if system:
            payload["system"] = True
        await emit(
            session,
            type="message.created",
            actor=acting,
            space_id=None,
            subject_type="message",
            subject_id=message.id,
            payload=payload,
        )
    stop: dict[str, object] = {"reason": reason.value, "detail": detail}
    if by is not None:
        stop["by"] = str(by)
    await steps.event(STOP_SEQ, EventKind.STOP, stop)
    await steps.done(run, reason.value)
    await _follow_up(session, steps, run)
    return reason


async def _follow_up(session: AsyncSession, steps: RunSteps, run: Run) -> None:
    """A run for the person's latest message after this run started, if no queued
    run answers it and the person may still ask the agent."""
    message_id = await ControlRepository(session, run.org_id).unanswered(run)
    if message_id is None:
        return
    agent = await steps.agent()
    person = await run_actor(session, run.org_id, run.user_id, run.agent_id)
    if agent is None or person is None or await refusal(session, person, agent) is not None:
        return
    await RunRepository(session, run.org_id).enqueue(
        run.agent_id, run.user_id, run.conversation_id, message_id
    )


def _target(connection: AiConnection, model: str) -> models.ModelTarget:
    """What the call needs of the connection, copied out of the row; the key is set
    when the client is made (`Executor._loop`)."""
    return models.ModelTarget(
        base_url=connection.base_url,
        rules=rules_for(ConnectionKind(connection.kind)),
        api_key=None,
        model=model,
        max_completion_tokens=connection.param_family == ParamFamily.MAX_COMPLETION_TOKENS,
        extra_body=dict(connection.extra_body),
        supports_tools=connection.supports_tools,
        proxy=egress_proxy(),
    )
