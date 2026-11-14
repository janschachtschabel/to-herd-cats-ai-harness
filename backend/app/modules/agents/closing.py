"""The end of a run, in one transaction (plan M5 task 6, M6, M7; the run's host:
`executor.py`): the answer (`kind=agent`, `client_id` = the run, so there is never a
second one), or on any other stop a timeline notice (`run.stopped` with the reason,
for the client to word), where the run answers (`place.py`: the DM, the mentioning
message's thread, the ticket's thread, an automation's place or the thread its term
opened); the run `done`. A heartbeat's answer `HEARTBEAT_OK` is delivered nowhere
(no message, no thread, no activity; its term's row notes it, plan M7 decision 7);
anything else a heartbeat's run delivers goes into the thread its term opens only
then. A ticket's run that ends without its answer (not cancelled)
gives the agent's responsible person an activity entry (`run_stopped`). A cancel
request found there wins over any other end (`cancelled`, no answer).

A DM's run leaves no question unanswered: a message the person sent after it started
that no queued run will answer (it came while the run waited) gets a run of its
own, queued in the same transaction; not after a cancelled run, which writes nothing
beyond its notice, nor after one a daily budget stopped (the next would stop at
once). An automation's run queues none (it answered no message): its end counts for
its automation instead (`automations/runs.ended`: three failures in a row pause it).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.actor import run_actor
from app.modules.agents.approvals.repository import WaitedRepository
from app.modules.agents.control_repository import ControlRepository
from app.modules.agents.executor_repository import Claimed, RunSteps
from app.modules.agents.models import EventKind, Run, StopReason
from app.modules.agents.notices import announce, notice, notify
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.run_repository import RunRepository
from app.modules.agents.standing import refusal
from app.modules.automations import runs as automation_runs
from app.modules.messaging import threads
from app.modules.messaging.models import MAX_BODY_CHARS, Message
from app.modules.messaging.notification_models import NotificationReason

STOP_KEY = "run.stopped"
STOP_SEQ = 0  # the stop's event; the steps' events count from 1
# A DM's run that ended so queues no run for what came meanwhile: a cancelled one
# writes nothing more; one stopped by a daily budget would stop again at once.
NO_FOLLOW_UP = frozenset({StopReason.CANCELLED, StopReason.BUDGET})


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
    quiet = (
        claimed.automation_id is not None
        and reason == StopReason.COMPLETED
        and await automation_runs.silent(session, claimed.org_id, claimed.id, answer)
    )
    root = None if quiet else await _thread(session, claimed)
    if reason == StopReason.COMPLETED:
        if answer is not None and not quiet:
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
    if claimed.automation_id is not None:
        await automation_runs.ended(session, claimed.org_id, claimed.automation_id, reason)
    elif reason not in NO_FOLLOW_UP and claimed.work_item_id is None and root is None:
        await _follow_up(session, steps, run)  # a DM's run
    return reason


async def _thread(session: AsyncSession, claimed: Claimed) -> Message | None:
    """The thread the run answers in, locked (None: the top level): a mention's
    thread, or the one an automation's term opened in a channel (a heartbeat's term
    opens it now)."""
    if claimed.trigger_message_id is not None:
        reads = ReadRepository(session, claimed.org_id)
        return await reads.thread_root(claimed.trigger_message_id, lock=True)
    if claimed.automation_id is not None:
        return await automation_runs.open_thread(session, claimed.org_id, claimed.id, lock=True)
    return None


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
