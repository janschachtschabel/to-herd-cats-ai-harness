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
- The end, in one transaction: the answer (`kind=agent`, `client_id` = the run, so
  there is never a second one), or on any other stop a timeline notice in the DM
  (`run.stopped` with the reason, for the client to word); the run `done`. A run whose
  question was deleted before it started (no person's message after the last answer)
  ends `completed` at once, without a call, an answer or a notice.

A worker that lost the run (its lease ran out and another worker took it) notices at
its next write and stops without writing anything (`Lost`). The provider's key is
resolved only now, for this attempt's client, and never stored or logged.
"""

import json
import time
from collections.abc import Callable
from dataclasses import replace

from app.core import secrets
from app.core.models_base import utcnow
from app.core.outbox import EventActor, emit
from app.core.principal import Principal
from app.modules.agents.actor import Reads, allowed_actor
from app.modules.agents.executor_repository import Claimed, RunSteps
from app.modules.agents.models import EventKind, StopReason
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.step_host import Lost, RunHost, Unit, Working
from app.modules.ai.models import AiConnection, ConnectionKind, ParamFamily
from app.modules.ai.provider import egress_proxy, rules_for
from app.modules.messaging.models import MAX_BODY_CHARS, Message
from app.modules.messaging.thread_repository import ThreadRepository
from app.runtime import context, models
from app.runtime.loop import Outcome, run_loop

MAX_ATTEMPTS = 3  # a run whose workers died this often stops with `error`
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
        """Work the run to its end; its stop reason, or None if it was lost."""
        try:
            prepared = await self._prepare(claimed)
            if isinstance(prepared, Outcome):
                return await self._finish(claimed, prepared)
            run, target, messages, instructions = prepared
            outcome = await self._loop(run, target, messages, instructions)
            return await self._finish(claimed, outcome)
        except Lost:
            return None

    async def _prepare(
        self, claimed: Claimed
    ) -> Outcome | tuple[Working, models.ModelTarget, context.Messages, str]:
        async with self.unit() as session:
            steps = RunSteps(session, claimed)
            if await steps.owned() is None:
                raise Lost
            agent = await steps.agent()
            if agent is None:
                return Outcome("rights_revoked")
            if claimed.attempt > MAX_ATTEMPTS:
                return Outcome("error", detail="attempts")
            org, user = claimed.org_id, claimed.user_id
            if await allowed_actor(session, org, user, agent, Reads()) is None:
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
            run = Working(claimed, agent, connection.id, connection.secret_ref, deadline)
        turns = [context.Turn("agent" if s.by_agent else "person", s.text) for s in said]
        instructions = context.instructions(agent.name, agent.instructions)
        return run, target, context.history(turns, instructions), instructions

    async def _loop(
        self,
        run: Working,
        target: models.ModelTarget,
        messages: context.Messages,
        instructions: str,
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
                use_tools=target.supports_tools,
            )
        finally:
            await built.close()

    async def _finish(self, claimed: Claimed, outcome: Outcome) -> StopReason:
        reason = StopReason(outcome.reason)
        async with self.unit() as session:
            steps = RunSteps(session, claimed)
            run = await steps.owned()
            if run is None:
                raise Lost
            acting = EventActor(claimed.org_id, Principal.agent(claimed.agent_id))
            message: Message | None = None
            system = False
            if reason == StopReason.COMPLETED:
                if outcome.answer is not None:
                    message = await steps.answer(outcome.answer[:MAX_BODY_CHARS])
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
            stop = {"reason": reason.value, "detail": outcome.detail}
            await steps.event(STOP_SEQ, EventKind.STOP, stop)
            await steps.done(run, reason.value)
        return reason


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
