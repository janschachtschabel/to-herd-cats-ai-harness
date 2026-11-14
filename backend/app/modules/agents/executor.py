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
  (what it is asked there is that space's content), and a run in a page's thread has
  read that page (a page locked for AI ends it `policy_blocked` before any model
  call; a draft's thread marks its space's draft as read, `writing.carries_draft`);
  then a place in the connection's `requests_per_minute`.
- After every model call, in one transaction: the step's `run_event`, its usage
  (`record_usage`) and the step counter. The event's key (run, attempt, step) is
  unique and the transaction checks the attempt first, so a call is recorded once,
  whatever worker died when.
- Every tool call: the rights again, the tool through the services with the run's
  actor (`tools.py`), and its `run_event` with the full result. A step that cannot be
  recorded, or a tool that fails, ends the run with `error` at once (the call's usage
  is still recorded).
- The end, in one transaction: `closing.close`. A run whose question was deleted
  before it started (no person's message after the last answer, the mentioning
  message deleted, the ticket gone, the automation's term gone) ends `completed` at
  once, without a call, an answer or a notice.

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

from app.core import secrets
from app.modules.agents import briefing, place
from app.modules.agents.actor import allowed_actor
from app.modules.agents.closing import close
from app.modules.agents.control_repository import ControlRepository
from app.modules.agents.executor_repository import Claimed, RunSteps
from app.modules.agents.journal import replay
from app.modules.agents.models import StopReason
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.repository import AgentRepository
from app.modules.agents.standing import run_target
from app.modules.agents.step_host import Lost, RunHost, Suspended, Unit, Working
from app.modules.agents.toolbox.catalog import offered
from app.modules.agents.toolbox.policy import Grant, allowed
from app.modules.ai.budget_metrics import budget_stops
from app.modules.ai.models import AiConnection, ConnectionKind, DataLocation, ParamFamily
from app.modules.ai.provider import egress_proxy, rules_for
from app.runtime import context, models
from app.runtime.loop import Outcome, Recorded, run_loop

MAX_RECOVERIES = 2  # a run taken up again this often after its worker died: `error`

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
            where = await steps.conversation()
            place_space = where.space_id
            if place_space is not None:  # a channel's or a thread's: its policy counts
                journal.reads.spaces.add(place_space)
            if where.page_id is not None:  # a page's thread: its `no_ai` counts too
                journal.reads.pages.add(where.page_id)
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
            # a draft's thread (or a draft memory page) is its editors' alone: the mark
            drafts = await ReadRepository(session, org).draft_spaces(journal.reads.pages)
            journal.reads.drafts |= drafts
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
            agent.name,
            agent.instructions,
            briefed.sections,
            found.asker,
            found.automation_of,
            found.automation_kind,
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
            reason = await close(
                session, steps, run, StopReason(outcome.reason), outcome.answer, outcome.detail
            )
        if reason == StopReason.BUDGET:  # committed; the detail is the budget's scope
            budget_stops().labels(scope=outcome.detail or "unknown").inc()
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
