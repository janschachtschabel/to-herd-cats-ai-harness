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
  deleted (else `policy_blocked`); a run in a channel or a thread has read its space
  (what it is asked there is that space's content); then a place in the connection's
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
  run, so there is never a second one), or on any other stop a timeline notice
  (`run.stopped` with the reason, for the client to word), where the run answers
  (`place.py`: the DM, the mentioning message's thread, the ticket's thread); the run
  `done`. A ticket's run that ends without its answer (not cancelled) gives the
  agent's responsible person an activity entry (`run_stopped`). A cancel
  request found there wins over any other end (`cancelled`, no answer). A message the
  person sent after the run started that no queued run will answer (it came while the
  run waited) gets a run of its own, queued in the same transaction; not after a
  cancelled run, which writes nothing beyond its notice (a DM's run only). A run
  whose question was deleted before it started (no person's message after the last
  answer, the mentioning message deleted, the ticket gone) ends `completed` at once,
  without a call, an answer or a notice.

Taking a run up again (plan M6 decision 1): the run replays its journal (`journal.py`)
and goes on after its last recorded step, with what it had read restored; the
conversation it answers ends at its first start. A run that waits (a tool answered
`Wait`) ends this take-up without an end (`execute` gives None).

A worker that lost the run (its lease ran out and another worker took it) notices at
its next write and stops without writing anything (`Lost`). The provider's key is
resolved only now, for this take-up's client, and never stored or logged.
"""

import time
from collections.abc import Callable
from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.modules.agents import briefing, place
from app.modules.agents.actor import allowed_actor, run_actor
from app.modules.agents.approvals.repository import WaitedRepository
from app.modules.agents.control_repository import ControlRepository
from app.modules.agents.executor_repository import Claimed, RunSteps
from app.modules.agents.journal import replay
from app.modules.agents.models import EventKind, Run, StopReason
from app.modules.agents.notices import announce, notice, notify
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.repository import AgentRepository
from app.modules.agents.run_repository import RunRepository
from app.modules.agents.standing import refusal, run_target
from app.modules.agents.step_host import Lost, RunHost, Suspended, Unit, Working
from app.modules.agents.toolbox.catalog import offered
from app.modules.agents.toolbox.policy import Grant, allowed
from app.modules.ai.models import AiConnection, ConnectionKind, DataLocation, ParamFamily
from app.modules.ai.provider import egress_proxy, rules_for
from app.modules.messaging import threads
from app.modules.messaging.models import MAX_BODY_CHARS, Message
from app.modules.messaging.notification_models import NotificationReason
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
            place_space = (await steps.conversation()).space_id
            if place_space is not None:  # a channel's or a thread's: its policy counts
                journal.reads.spaces.add(place_space)
            conversation = claimed.conversation_id
            actor = await allowed_actor(session, org, user, agent, journal.reads, conversation)
            if actor is None:
                return Outcome("rights_revoked")
            uses = await run_target(session, org, agent)  # a personal agent: its owner's now
            assert uses is not None  # agent_refusal checked it
            connection = await steps.connection(uses.connection_id)
            assert connection is not None  # agent_refusal checked it
            location = DataLocation(connection.data_location)
            briefed = await briefing.brief(session, actor, agent, location, place_space)
            journal.reads.spaces |= briefed.spaces  # the memory it gets is read
            journal.reads.pages |= briefed.pages
            found = await place.asked(session, claimed)
            if found is None:  # its question was deleted: nothing to answer
                return Outcome("completed")
            target = _target(connection, uses.model)
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
                reply_to=found.reply_to,
            )
        instructions = context.instructions(
            agent.name, agent.instructions, briefed.sections, found.asker
        )
        history = context.history(found.turns, instructions)
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
    root = None
    if claimed.trigger_message_id is not None:
        reads = ReadRepository(session, claimed.org_id)
        root = await reads.thread_root(claimed.trigger_message_id, lock=True)
    if reason == StopReason.COMPLETED:
        if answer is not None:
            message = await steps.answer(answer[:MAX_BODY_CHARS], root)
            if message is not None:
                if root is not None:
                    threads.count_reply(root, message)
                    await session.flush()
                await announce(session, claimed.org_id, claimed.agent_id, message)
    else:
        content = {"key": STOP_KEY, "actor": str(claimed.agent_id), "to": reason.value}
        conversation = await steps.conversation()
        message = await notice(
            session, claimed.org_id, claimed.agent_id, conversation, claimed.id, content, root
        )
        if message is not None and claimed.work_item_id is not None and by is None:
            await _tell_responsible(session, steps, message)
    stop: dict[str, object] = {"reason": reason.value, "detail": detail}
    if by is not None:
        stop["by"] = str(by)
    await steps.event(STOP_SEQ, EventKind.STOP, stop)
    await WaitedRepository(session, claimed.org_id).expire_pending(run.id)
    await steps.done(run, reason.value)
    if reason != StopReason.CANCELLED and claimed.work_item_id is None and root is None:
        await _follow_up(session, steps, run)  # a DM's run (cancelled: nothing more)
    return reason


async def _tell_responsible(session: AsyncSession, steps: RunSteps, message: Message) -> None:
    """A ticket's run ended without its answer: the agent's responsible person learns
    of it (`run_stopped`)."""
    agent = await steps.agent()
    if agent is not None:
        reason = NotificationReason.RUN_STOPPED
        user_id = agent.responsible_user_id
        await notify(session, agent.org_id, agent.id, message, user_id, reason)


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
