"""One term of an automation (plan M7 decisions 2 to 6, 10, 13), in the caller's
transaction with the automation's row locked: the due loop's (`firing.py`) and an
event rule's (`event_rules.py`). The run (or the note why none), the term's row in
the log and, where it belongs, the term's system entry commit together. What comes
next (the next term, the quiet time) is the caller's.

In this order:

- The agent not active (paused, or a draft): no run, `skipped_paused_agent`.
- The owner may no longer run it (`standing.owner_may_run`: deactivated, no
  `ai.use`, the agent or the place out of reach): the automation is paused
  (`paused_reason = owner`, `pausing.py`), nothing is logged and it keeps the term.
- The agent may not run for another reason (its responsible person inactive, its
  connection unavailable, personal agents switched off): `skipped_paused_agent`.
- The place is archived or closed to the agent's connection by its space's AI
  policy: `skipped_policy`. A daily budget of the owner, the agent or the
  organisation is reached (`ai.budgets`): `skipped_budget`.
- The automation's previous run still open (queued, running or waiting; its lane
  is the automation): no run, `skipped_busy`.
- Otherwise a queued run like any other, which the run loop takes up: asked by the
  owner (`run.user_id`), at the automation's place (`run.conversation_id`), in the
  automation's lane, at the chain's depth the caller names (0 but for a run an
  event of another run started, decision 9). The log keeps the instruction it is
  given (`runs.py` reads it). In a channel or a ticket's thread a system entry
  `automation.started` opens the term (`entries.py`): in a channel it is the root of
  the thread the run answers in, one thread per term (decision 3). A heartbeat's
  term opens nothing yet: its run posts the entry only when it has something to
  deliver (`runs.open_thread`), since an answer `HEARTBEAT_OK` leaves no trace.

Whatever the outcome of a logged term, the automation's watchers hear of it
(`live.fired`); a pause tells them by itself (`pausing.py`).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.modules.agents.models import Agent, AgentStatus
from app.modules.agents.repository import AgentRepository
from app.modules.agents.run_repository import RunRepository
from app.modules.agents.standing import agent_refusal, run_target
from app.modules.ai.budgets import budget_exhausted, has_price
from app.modules.ai.models import AiConnection
from app.modules.automations import entries, live, pausing
from app.modules.automations.models import (
    Automation,
    AutomationKind,
    FiringOutcome,
    PausedReason,
)
from app.modules.automations.repository import AutomationRepository
from app.modules.automations.standing import owner_may_run, place_closed
from app.modules.messaging.models import Conversation, ConversationKind


@dataclass(frozen=True, slots=True)
class Fired:
    automation_id: uuid.UUID
    due_at: datetime
    outcome: FiringOutcome | None  # None: paused instead (`paused`)
    run_id: uuid.UUID | None
    paused: PausedReason | None = None
    firing_id: uuid.UUID | None = None  # the term's row in the log (None: paused)

    @property
    def label(self) -> str:
        """For the metric: the outcome, or `paused_<reason>`."""
        return self.outcome.value if self.outcome else f"paused_{self.paused}"


async def fire(
    session: AsyncSession,
    automation: Automation,
    due_at: datetime,
    now: datetime,
    *,
    chain_depth: int = 0,
) -> Fired:
    automations = AutomationRepository(session, automation.org_id)
    place = await automations.place(automation)
    agent = await AgentRepository(session, automation.org_id).get(automation.agent_id)
    assert agent is not None  # the automation goes with its agent
    if agent.status == AgentStatus.ACTIVE and not await owner_may_run(
        session, automation.owner_user_id, agent, place
    ):
        await pausing.pause(session, automation, PausedReason.OWNER)
        return Fired(automation.id, due_at, None, None, PausedReason.OWNER)
    firing_id = uuid7()
    outcome, run_id = await _start(session, automation, agent, place, now, chain_depth)
    await automations.log(automation, due_at, now, outcome, run_id, firing_id=firing_id)
    await live.fired(session, automation)
    heartbeat = automation.kind == AutomationKind.HEARTBEAT
    if outcome == FiringOutcome.STARTED and place.kind != ConversationKind.DM and not heartbeat:
        await entries.opened(session, automation, place, firing_id)
    return Fired(automation.id, due_at, outcome, run_id, firing_id=firing_id)


async def _start(
    session: AsyncSession,
    automation: Automation,
    agent: Agent,
    place: Conversation,
    now: datetime,
    chain_depth: int,
) -> tuple[FiringOutcome, uuid.UUID | None]:
    org = automation.org_id
    if agent.status != AgentStatus.ACTIVE or await agent_refusal(session, org, agent):
        return FiringOutcome.SKIPPED_PAUSED_AGENT, None
    target = await run_target(session, org, agent)
    assert target is not None  # agent_refusal checked it
    connection = await session.get(AiConnection, target.connection_id)
    if await place_closed(session, place, connection):
        return FiringOutcome.SKIPPED_POLICY, None
    priced = has_price(connection, target.model)
    owner = automation.owner_user_id
    if await budget_exhausted(session, org, owner, agent.id, priced=priced, now=now):
        return FiringOutcome.SKIPPED_BUDGET, None
    run_id = await RunRepository(session, org).start(
        agent.id,
        owner,
        place.id,
        lane_id=automation.id,
        automation_id=automation.id,
        chain_depth=chain_depth,
    )
    if run_id is None:
        return FiringOutcome.SKIPPED_BUSY, None
    return FiringOutcome.STARTED, run_id
