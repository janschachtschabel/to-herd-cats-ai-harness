"""Firing a due automation (plan M7 decisions 1 to 6, 10, 13): what the due loop does
with one term, in the caller's transaction, so that the term's run (or the note
that it was skipped), its row in the log and the automation's next term commit
together or not at all. Any number of workers may fire at once: the automation's
row is locked while its term fires (`claim_due`) and the log takes a term once.

In this order:

- A heartbeat's term taken up after its window closed (an outage): no run,
  `skipped_off_hours` (`heartbeats.py`).
- The agent not active (paused, or a draft): no run, `skipped_paused_agent`.
- The owner may no longer run it (`standing.owner_may_run`: deactivated, no
  `ai.use`, the agent or the place out of reach): the automation is paused
  (`paused_reason = owner`, `pausing.py`), nothing is logged and it keeps the
  term, which fires once it runs again.
- The agent may not run for another reason (its responsible person inactive, its
  connection unavailable, personal agents switched off): `skipped_paused_agent`.
- The place is archived or closed to the agent's connection by its space's AI
  policy: `skipped_policy`. A daily budget of the owner, the agent or the
  organisation is reached (`ai.budgets`): `skipped_budget`.
- The automation's previous run still open (queued, running or waiting; its lane
  is the automation): no run, `skipped_busy`.
- Otherwise a queued run like any other, which the run loop takes up: asked by the
  owner (`run.user_id`), at the automation's place (`run.conversation_id`), in the
  automation's lane, at the top of no chain (`chain_depth` 0). The log keeps the
  instruction it is given (`runs.py` reads it). In a channel or a ticket's thread
  a system entry `automation.started` (the owner as its actor, the automation's
  id; never the instruction) opens the term: in a channel it is the root of the
  thread the run answers in, one thread per term (decision 3). A heartbeat's term
  opens nothing yet: its run posts the entry only when it has something to deliver
  (`runs.open_thread`), since an answer `HEARTBEAT_OK` leaves no trace.

A `once` is done after its term, whatever the outcome; a recurring automation takes
the first term after "now" (`terms.next_term`), a heartbeat the next in its active
hours (`heartbeat_terms.py`), so after an outage either fires once for all the terms
it missed.
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
from app.modules.automations import entries, heartbeats, pausing, terms
from app.modules.automations.models import (
    Automation,
    AutomationKind,
    FiringOutcome,
    PausedReason,
)
from app.modules.automations.repository import AutomationRepository, claim_due
from app.modules.automations.standing import owner_may_run, place_closed
from app.modules.messaging.models import Conversation, ConversationKind


@dataclass(frozen=True, slots=True)
class Fired:
    automation_id: uuid.UUID
    due_at: datetime
    outcome: FiringOutcome | None  # None: paused instead (`paused`)
    run_id: uuid.UUID | None
    paused: PausedReason | None = None

    @property
    def label(self) -> str:
        """For the metric: the outcome, or `paused_<reason>`."""
        return self.outcome.value if self.outcome else f"paused_{self.paused}"


async def fire_next(session: AsyncSession, now: datetime) -> Fired | None:
    """Fire the most overdue automation due at `now` that no other worker holds;
    None: none is due. The caller commits."""
    automation = await claim_due(session, now)
    if automation is None:
        return None
    assert automation.next_due_at is not None  # an active automation has a term
    due_at = automation.next_due_at
    automations = AutomationRepository(session, automation.org_id)
    if heartbeats.off_hours(automation, due_at, now):
        outcome = FiringOutcome.SKIPPED_OFF_HOURS
        await automations.log(automation, due_at, now, outcome)
        await automations.advance(automation, _next_due(automation, now))
        return Fired(automation.id, due_at, outcome, None)
    place = await automations.place(automation)
    agent = await AgentRepository(session, automation.org_id).get(automation.agent_id)
    assert agent is not None  # the automation goes with its agent
    if agent.status == AgentStatus.ACTIVE and not await owner_may_run(
        session, automation.owner_user_id, agent, place
    ):
        await pausing.pause(session, automation, PausedReason.OWNER)
        return Fired(automation.id, due_at, None, None, PausedReason.OWNER)
    firing_id = uuid7()
    outcome, run_id = await _start(session, automation, agent, place, now)
    await automations.log(automation, due_at, now, outcome, run_id, firing_id=firing_id)
    heartbeat = automation.kind == AutomationKind.HEARTBEAT
    if outcome == FiringOutcome.STARTED and place.kind != ConversationKind.DM and not heartbeat:
        await entries.opened(session, automation, place, firing_id)
    await automations.advance(automation, _next_due(automation, now))
    return Fired(automation.id, due_at, outcome, run_id)


async def _start(
    session: AsyncSession,
    automation: Automation,
    agent: Agent,
    place: Conversation,
    now: datetime,
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
        agent.id, owner, place.id, lane_id=automation.id, automation_id=automation.id
    )
    if run_id is None:
        return FiringOutcome.SKIPPED_BUSY, None
    return FiringOutcome.STARTED, run_id


def _next_due(automation: Automation, now: datetime) -> datetime | None:
    if automation.kind == AutomationKind.ONCE:
        return None
    if automation.kind == AutomationKind.HEARTBEAT:
        return heartbeats.next_term(automation, now)
    assert automation.cron is not None and automation.time_zone is not None
    return terms.next_term(automation.cron, automation.time_zone, now)
