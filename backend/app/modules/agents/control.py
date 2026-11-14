"""Steering runs from outside their worker (plan M6 decision 1 and 12): resuming a run
that waits, asking a run to stop, and ending waiting runs whose time ran out.

- `resume_waiting`, for the answer to what a run waits for (a release, a question:
  M6 tasks 7 and later), in the transaction that records the answer: the run is
  `queued` again and keeps its journal; the next take-up replays it and runs the tool
  call it waited on once more, which now finds its answer. A DM's queued run that had
  come in behind it and never started is dropped; what it would have answered, the
  run queues when it ends (`closing.close`). Nothing else is dropped: another
  thread's run in a channel has its own lane, and a ticket handed over to another
  agent keeps the run that follows. Nothing wakes the workers here: the answer's
  own outbox event does, else they look within a second.
- `request_cancel` records the request once (`run_cancel_request`). Who may ask is the
  caller's rule. The run's row is locked first (`FOR NO KEY UPDATE`, waiting at most
  `REASSIGN_LOCK_TIMEOUT_SECONDS`, else 409 `conflict.retry`), so a run that ends at
  the same moment either ends `cancelled` or was done before (False). A running run stops before its
  next step; a queued one when it is taken up; a waiting one at the next sweep.
- `cancel` (the run view's `POST /api/runs/{id}/cancel`, M6 task 10): the same
  request, and a run nobody works on (queued or waiting) ends `cancelled` at once, in
  the same transaction, with its notice; a running one stops before its next step or
  at its end. Asking again answers the same; a run that ended otherwise first: False.
  It waits for the run's row as briefly as `request_cancel` (409 `conflict.retry`;
  plan M7 decision 15).
  No worker needs waking: the run that ends here needs none, and the notice's outbox
  event wakes the loops anyway.
- `sweep_waiting`, from the run loop: waiting runs past `wait_until` end with
  `approval_expired` when they wait for a release, else `waiting_timeout`; those
  someone asked to stop with `cancelled`; each with its notice in the conversation,
  like any other end (and what they waited for is `expired`); each in a savepoint, so
  one that cannot be ended keeps no other from ending.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.agents.approvals.repository import WaitedRepository
from app.modules.agents.closing import close
from app.modules.agents.control_repository import ControlRepository, due_waiting
from app.modules.agents.executor_repository import Claimed, RunSteps
from app.modules.agents.models import REASSIGN_LOCK_TIMEOUT_SECONDS, RunState, StopReason

SWEEP_BATCH = 50

logger = logging.getLogger(__name__)


async def resume_waiting(session: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID) -> bool:
    """Queue the waiting run again (False: it does not wait, nothing changed)."""
    repo = ControlRepository(session, org_id)
    run = await repo.lock(run_id)
    if run is None or run.state != RunState.WAITING:
        return False
    await repo.drop_queued(run)
    run.state = RunState.QUEUED
    run.wait_until = None
    await session.flush()
    return True


async def request_cancel(
    session: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Ask the run to stop (False: it is done already). The run's row is waited for
    briefly (a step of the run holds it while it works): 409 `conflict.retry` after
    `REASSIGN_LOCK_TIMEOUT_SECONDS`, for the person to send the request again."""
    repo = ControlRepository(session, org_id)
    run = await repo.lock_briefly(run_id, REASSIGN_LOCK_TIMEOUT_SECONDS)
    if run is None or run.state == RunState.DONE:
        return False
    await repo.add_cancel_request(run.id, user_id)
    return True


async def cancel(
    session: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Stop the run, now if nobody works on it (False: it ended otherwise first). The
    run's row is waited for briefly, as in `request_cancel` (plan M7 decision 15)."""
    repo = ControlRepository(session, org_id)
    run = await repo.lock_briefly(run_id, REASSIGN_LOCK_TIMEOUT_SECONDS)
    if run is None:
        return False
    if run.state == RunState.DONE:
        return run.stop_reason == StopReason.CANCELLED
    await repo.add_cancel_request(run.id, user_id)
    if run.state in (RunState.QUEUED, RunState.WAITING):
        await close(session, RunSteps(session, Claimed.of(run)), run, StopReason.CANCELLED)
    return True


async def sweep_waiting(session: AsyncSession) -> int:
    """End the waiting runs that are due (the caller commits); how many ended. Each in
    a savepoint of its own: one whose end fails stays waiting (logged, ids and the
    error class only) and is tried again at the next sweep; the others end."""
    ended = 0
    for run in await due_waiting(session, utcnow(), SWEEP_BATCH):
        try:
            async with session.begin_nested():
                steps = RunSteps(session, Claimed.of(run))
                released = await WaitedRepository(session, run.org_id).pending_approval(run.id)
                reason = StopReason.APPROVAL_EXPIRED if released else StopReason.WAITING_TIMEOUT
                await close(session, steps, run, reason)
        except Exception as exc:
            error = type(exc).__name__
            logger.warning("runs.sweep_failed", extra={"run_id": str(run.id), "error": error})
            continue
        ended += 1
    return ended
