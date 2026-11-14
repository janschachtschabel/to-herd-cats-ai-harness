"""Runs that start from a mention and from a ticket assignment (plan M6 decision 6,
task 8); a DM's runs: `hooks.py`.

- **Mention**: a person's new message in a channel, a page thread or a ticket thread
  that mentions an agent (its id among the message's `mentions`) starts a run of the
  first mentioned agent that is a member of the conversation's space and no draft, if
  the person has `ai.use`. Without `ai.use`, or for an id that is no such agent,
  nothing starts and the answer says nothing (`agent_run` stays null, the id is "not
  notified" like any id that is no person). Otherwise a refusal names its code
  (`standing.Refusal`: the agent paused, its responsible person inactive, its
  connection unavailable; `run.waiting` while its lane has a run queued, running or
  waiting). The lane, where one run may be open at a time, is the thread of the
  mentioning message in a channel (`run.lane_id`, its root), so a run waiting for a
  release holds its thread, not the channel; in a page or a ticket thread it is the
  whole conversation (one run per page, one per ticket). The run answers in the
  thread of the mentioning message (`place.reply_to`). An agent's message mentions nobody, so
  agents mentioning agents start nothing; editing a message to mention an agent
  starts nothing either.
- **Ticket assignment**: a ticket assigned to an agent (`tickets/assignment.py` let
  it: `ticket.assign`, `ai.use`, the agent a member with a role that edits tickets)
  starts a run whose place is the ticket's thread, whose task is the ticket
  (`work_item_id`), asked by the person who assigned it. Its answer is a comment in
  the thread. If it cannot start (a refusal, or another run already open in the
  thread: one run per ticket), the ticket stays assigned, the thread names why (a
  notice `run.refused`: the agent as its actor, the code in `to`) and the agent's
  responsible person gets an activity entry (`run_stopped`).
- **Handover**: an agent's run that assigns the ticket to another agent
  (`assign_ticket`) starts that agent's run for the same person (the run acts as the
  person who asked the first run, so `user_id` stays theirs), one link further down
  the chain (`chain_depth` + 1). A run at `MAX_CHAIN_DEPTH` hands over no more: the
  tool refuses and the thread notes it (`ticket_tools.assign_ticket`).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.authorship import Authorship
from app.modules.agents.models import Agent
from app.modules.agents.notices import notice, notify
from app.modules.agents.repository import AgentRepository
from app.modules.agents.run_repository import RunRepository
from app.modules.agents.standing import Refusal, refusal
from app.modules.messaging.agent_hooks import RunStart
from app.modules.messaging.models import Conversation, ConversationKind, Message
from app.modules.messaging.notification_models import NotificationReason
from app.modules.tickets.models import WorkItem
from app.modules.tickets.thread_repository import TicketThreadRepository

REFUSED_KEY = "run.refused"


async def on_mention(
    session: AsyncSession,
    actor: Actor,
    conversation: Conversation,
    message: Message,
    mentioned: list[uuid.UUID],
) -> RunStart | None:
    if conversation.space_id is None or not mentioned:
        return None
    if not await can(session, actor, Action.AI_USE):
        return None
    agent = await AgentRepository(session, actor.org_id).first_member(
        mentioned, conversation.space_id
    )
    if agent is None:
        return None
    why = await refusal(session, actor, agent)
    if why == Refusal.NOT_FOUND:  # someone else's personal agent: tell nothing
        return None
    if why is not None:
        return RunStart(None, why.value, agent.id)
    channel = conversation.kind == ConversationKind.CHANNEL
    run_id = await RunRepository(session, actor.org_id).start(
        agent.id,
        actor.principal.id,
        conversation.id,
        message_id=message.id,
        lane_id=(message.parent_id or message.id) if channel else None,
    )
    if run_id is None:
        return RunStart(None, Refusal.RUN_WAITING.value, agent.id)
    return RunStart(run_id, None, agent.id)


async def on_assignment(
    session: AsyncSession, actor: Actor, ticket: WorkItem, by: Authorship | None
) -> None:
    assert ticket.assignee_id is not None
    agent = await AgentRepository(session, actor.org_id).get(ticket.assignee_id)
    assert agent is not None  # `assignable` found it
    runs = RunRepository(session, actor.org_id)
    handing = await runs.of_run(by.run_id) if by is not None and by.run_id else None
    depth = handing.chain_depth + 1 if handing is not None else 0
    thread = await TicketThreadRepository(session, actor.org_id).thread_for(ticket)
    why = await refusal(session, actor, agent)
    if why is None:
        run_id = await runs.start(
            agent.id,
            actor.principal.id,
            thread.id,
            work_item_id=ticket.id,
            chain_depth=depth,
            besides=handing.id if handing is not None else None,
        )
        if run_id is not None:
            return
        why = Refusal.RUN_WAITING
    await refused(session, agent, thread, why.value)


async def refused(session: AsyncSession, agent: Agent, thread: Conversation, code: str) -> None:
    """The ticket's thread names why the agent's run did not start, and the agent's
    responsible person learns of it."""
    content = {"key": REFUSED_KEY, "actor": str(agent.id), "to": code}
    message = await notice(session, agent.org_id, agent.id, thread, uuid.uuid4(), content)
    assert message is not None  # a fresh id
    reason = NotificationReason.RUN_STOPPED
    await notify(session, agent.org_id, agent.id, message, agent.responsible_user_id, reason)
