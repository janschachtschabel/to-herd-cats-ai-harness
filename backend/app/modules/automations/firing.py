"""Firing a due automation (plan M7 decisions 1, 5 and 6): what the due loop does
with one term, in the caller's transaction, so that the term's run (or the note
that it was skipped), its row in the log and the automation's next term commit
together or not at all. Any number of workers may fire at once: the automation's
row is locked while its term fires (`claim_due`) and the log takes a term once.

- The agent not active (paused, or a draft): no run, `skipped_paused_agent`.
- The automation's previous run still open (queued, running or waiting; its lane
  is the automation): no run, `skipped_busy`.
- Otherwise a queued run like any other, which the run loop takes up: asked by the
  owner (`run.user_id`), at the automation's place (`run.conversation_id`), in the
  automation's lane, at the top of no chain (`chain_depth` 0).

A `once` is done after its term, whatever the outcome; a recurring automation takes
the first term after "now" (`terms.next_term`), so after an outage it fires once
for all the terms it missed.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import AgentStatus
from app.modules.agents.repository import AgentRepository
from app.modules.agents.run_repository import RunRepository
from app.modules.automations import terms
from app.modules.automations.models import Automation, AutomationKind, FiringOutcome
from app.modules.automations.repository import AutomationRepository, claim_due


@dataclass(frozen=True, slots=True)
class Fired:
    automation_id: uuid.UUID
    due_at: datetime
    outcome: FiringOutcome
    run_id: uuid.UUID | None


async def fire_next(session: AsyncSession, now: datetime) -> Fired | None:
    """Fire the most overdue automation due at `now` that no other worker holds;
    None: none is due. The caller commits."""
    automation = await claim_due(session, now)
    if automation is None:
        return None
    assert automation.next_due_at is not None  # an active automation has a term
    due_at = automation.next_due_at
    outcome, run_id = await _start(session, automation)
    automations = AutomationRepository(session, automation.org_id)
    await automations.log(automation, due_at, now, outcome, run_id)
    await automations.advance(automation, _next_due(automation, now))
    return Fired(automation.id, due_at, outcome, run_id)


async def _start(
    session: AsyncSession, automation: Automation
) -> tuple[FiringOutcome, uuid.UUID | None]:
    org = automation.org_id
    agent = await AgentRepository(session, org).get(automation.agent_id)
    if agent is None or agent.status != AgentStatus.ACTIVE:
        return FiringOutcome.SKIPPED_PAUSED_AGENT, None
    run_id = await RunRepository(session, org).start(
        agent.id,
        automation.owner_user_id,
        automation.conversation_id,
        lane_id=automation.id,
        automation_id=automation.id,
    )
    if run_id is None:
        return FiringOutcome.SKIPPED_BUSY, None
    return FiringOutcome.STARTED, run_id


def _next_due(automation: Automation, now: datetime) -> datetime | None:
    if automation.kind == AutomationKind.ONCE:
        return None
    assert automation.cron is not None and automation.time_zone is not None
    return terms.next_term(automation.cron, automation.time_zone, now)
