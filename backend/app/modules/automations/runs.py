"""What an automation's run reads of its automation, and what its end does to it
(plan M7 decisions 3 and 13); the run itself is the agents' (`agents/place.py`,
`agents/executor.py`), which ask here.

- `assignment`: the instruction the run was given (kept in the log row of the term
  that started it, so every take-up reads the same, whatever the owner edits
  meanwhile) and, in a channel, the thread the term opened (its system entry, the
  root the run answers in), its automation's kind and, for an event rule's run, what
  it is told of the events its term took (`EventNote`: the kind, the ids of the
  objects, how many), copied to the term's row as it fired, whatever the rule says
  now. Never derived from `run.lane_id`, which is the automation.
- `open_thread`: where the run delivers, in a channel the thread its term opened. A
  heartbeat's term opens nothing when it fires: the first delivery of its run (its
  answer, a card, the notice of its end) posts the term's entry first
  (`entries.py`), so a heartbeat that answers `HEARTBEAT_OK` leaves no trace.
- `heard_in_place`: whether the run's progress goes live to its place (a heartbeat's
  only once it has delivered something; until then to its owner alone).
- `silent`: in the transaction that ends the run, whether its answer is a
  heartbeat's `HEARTBEAT_OK`, which is delivered nowhere; the term's row notes it
  (`heartbeat_ok`).
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
from app.modules.automations import entries, heartbeats, pausing
from app.modules.automations.event_models import EventNote
from app.modules.automations.models import AutomationKind, AutomationState, PausedReason
from app.modules.automations.repository import AutomationRepository
from app.modules.messaging.models import ConversationKind, Message

FAILING_STREAK = 3
NOT_COUNTED = frozenset({StopReason.CANCELLED, StopReason.BUDGET})


@dataclass(frozen=True, slots=True)
class Assignment:
    instruction: str
    thread: Message | None  # the thread it answers in (None: at the top level)
    kind: AutomationKind | None = None  # its automation's (None: gone)
    event: EventNote | None = None  # an event rule's run


async def assignment(
    session: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID, *, lock: bool = False
) -> Assignment | None:
    """None: the run's term is gone (its automation deleted)."""
    repo = AutomationRepository(session, org_id)
    firing = await repo.firing_of(run_id)
    if firing is None or firing.instruction is None:
        return None
    automation = await repo.get(firing.automation_id)
    kind = automation.kind if automation is not None else None
    note = None
    if firing.event_type is not None:
        assert firing.event_count is not None and firing.event_objects is not None
        note = EventNote(firing.event_type, firing.event_count, list(firing.event_objects))
    thread = await repo.thread_of(firing.id, lock=lock)
    return Assignment(firing.instruction, thread, kind, note)


async def open_thread(
    session: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID, *, lock: bool = False
) -> Message | None:
    """The thread the run delivers in (None: the top level, or no automation's run);
    a heartbeat's term's entry is posted now if it is not yet."""
    repo = AutomationRepository(session, org_id)
    firing = await repo.firing_of(run_id)
    if firing is None:
        return None
    automation = await repo.get(firing.automation_id)
    if automation is None:
        return None
    place = await repo.place(automation)
    if automation.kind == AutomationKind.HEARTBEAT and place.kind != ConversationKind.DM:
        if await repo.entry_of(firing.id) is None:
            await entries.opened(session, automation, place, firing.id)
    return await repo.thread_of(firing.id, lock=lock)


async def heard_in_place(session: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID) -> bool:
    """Whether the run's progress goes live to its place: any run but a heartbeat's
    before its first delivery (its term's entry not yet posted; in a DM, never before
    its end), which would put an "is working" card in front of the place's readers at
    every interval for an answer that may be `HEARTBEAT_OK` (review M7, finding 5)."""
    repo = AutomationRepository(session, org_id)
    firing = await repo.firing_of(run_id)
    if firing is None:
        return True
    automation = await repo.get(firing.automation_id)
    if automation is None or automation.kind != AutomationKind.HEARTBEAT:
        return True
    return await repo.entry_of(firing.id) is not None


async def silent(
    session: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID, answer: str | None
) -> bool:
    """Whether the run's answer is a heartbeat's `HEARTBEAT_OK` (then noted in its
    term's row, and delivered nowhere)."""
    if not heartbeats.is_ok(answer):
        return False
    repo = AutomationRepository(session, org_id)
    firing = await repo.firing_of(run_id)
    if firing is None:
        return False
    automation = await repo.get(firing.automation_id)
    if automation is None or automation.kind != AutomationKind.HEARTBEAT:
        return False
    firing.heartbeat_ok = True
    await session.flush()
    return True


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
