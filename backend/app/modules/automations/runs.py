"""What an automation's run reads of its automation, and what its end does to it
(plan M7 decisions 3 and 13); the run itself is the agents' (`agents/place.py`,
`agents/executor.py`), which ask here.

- `assignment`: the instruction the run was given (kept in the log row of the term
  that started it, so every take-up reads the same, whatever the owner edits
  meanwhile) and, in a channel, the thread the term opened (its system entry, the
  root the run answers in). Never derived from `run.lane_id`, which is the
  automation.
- `ended`: in the transaction that ends the run. A run that did not end `completed`
  counts (`automation.failures`); the third in a row pauses the automation
  (`failing`, the owner learns of it). A completed run starts the count anew. A
  cancelled run (someone stopped it) and one a daily budget stopped say nothing
  about the automation: they neither count nor start the count anew.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import StopReason
from app.modules.automations import pausing
from app.modules.automations.models import AutomationState, PausedReason
from app.modules.automations.repository import AutomationRepository
from app.modules.messaging.models import Message

FAILING_STREAK = 3
NOT_COUNTED = frozenset({StopReason.CANCELLED, StopReason.BUDGET})


@dataclass(frozen=True, slots=True)
class Assignment:
    instruction: str
    thread: Message | None  # the thread it answers in (None: at the top level)


async def assignment(
    session: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID, *, lock: bool = False
) -> Assignment | None:
    """None: the run's term is gone (its automation deleted)."""
    repo = AutomationRepository(session, org_id)
    firing = await repo.firing_of(run_id)
    if firing is None or firing.instruction is None:
        return None
    return Assignment(firing.instruction, await repo.thread_of(firing.id, lock=lock))


async def ended(
    session: AsyncSession, org_id: uuid.UUID, automation_id: uuid.UUID, reason: StopReason
) -> None:
    if reason in NOT_COUNTED:
        return
    repo = AutomationRepository(session, org_id)
    automation = await repo.get(automation_id, lock=True)
    if automation is None:
        return
    if reason == StopReason.COMPLETED:
        automation.failures = 0
    else:
        automation.failures += 1
    if automation.failures >= FAILING_STREAK and automation.state == AutomationState.ACTIVE:
        automation.failures = 0
        await pausing.pause(session, automation, PausedReason.FAILING)
    await session.flush()
