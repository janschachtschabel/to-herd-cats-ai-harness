"""What messaging and tickets ask of agents (`messaging/agent_hooks.py`,
`tickets/agent_hooks.py`), registered on import
(by the agent routes and the worker's handlers; not by the package, whose models the
core's repositories import).

A new top-level message of the person in a DM with an agent queues a run in the
message's own transaction, if the person and the agent may (`standing.refusal`);
otherwise the message stays without one and the answer says why. Replies in a thread
start nothing, and so does a message while the conversation's run waits for a
person's answer (`run.waiting`: that run answers first, and when it ends it queues a
run for what came meanwhile).

A person's new message elsewhere that mentions an agent, and a ticket assigned to an
agent, start runs too (`triggers.py`, plan M6 task 8). A ticket taken from an agent
(given to someone else or nobody) asks that agent's open runs on it to stop, in the
same transaction, through their cancel request (`control.request_cancel`); the run
that hands it over itself goes on (review M6 finding 16b).

Tickets go to an agent (plan M6 decision 7) only from someone with `ai.use`, and only
to an agent that is no draft and a member of the ticket's space with a role that may
edit tickets there (it should comment and move the status); a personal agent only
from its owner (an agent's handover acts as the person who asked, so the same holds).
"""

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, can
from app.core.actor import Actor
from app.core.authorship import Authorship
from app.core.permissions import SPACE_ACTION_MIN_ROLE
from app.core.principal import PrincipalType
from app.modules.agents import control, triggers
from app.modules.agents.models import AgentStatus
from app.modules.agents.repository import AgentRepository
from app.modules.agents.run_repository import RunRepository
from app.modules.agents.standing import Refusal, owned_by, refusal, visible_agent
from app.modules.messaging.agent_hooks import RunStart, register_agent_hooks
from app.modules.messaging.models import Conversation, ConversationKind, Message
from app.modules.tickets.agent_hooks import register_assignee_hooks
from app.modules.tickets.models import WorkItem


class _Hooks:
    async def require_addressable(
        self, session: AsyncSession, actor: Actor, agent_id: uuid.UUID
    ) -> None:
        await visible_agent(session, actor, agent_id)

    async def after_post(
        self,
        session: AsyncSession,
        actor: Actor,
        conversation: Conversation,
        message: Message,
        mentioned: list[uuid.UUID],
    ) -> RunStart | None:
        if actor.principal.type != PrincipalType.USER:
            return None
        if conversation.kind != ConversationKind.DM:
            return await triggers.on_mention(session, actor, conversation, message, mentioned)
        agent = await AgentRepository(session, actor.org_id).of_conversation(conversation.id)
        if agent is None:
            return None
        if message.parent_id is not None:
            return RunStart(None, Refusal.THREAD_REPLY.value, agent.id)
        why = await refusal(session, actor, agent)
        if why is not None:
            return RunStart(None, why.value, agent.id)
        runs = RunRepository(session, actor.org_id)
        if await runs.waiting(conversation.id):
            return RunStart(None, Refusal.RUN_WAITING.value, agent.id)
        run_id = await runs.enqueue(agent.id, actor.principal.id, conversation.id, message.id)
        return RunStart(run_id, None, agent.id)

    async def names(
        self, session: AsyncSession, org_id: uuid.UUID, ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        return await AgentRepository(session, org_id).names(set(ids))


class _Assignees:
    async def assignable(
        self, session: AsyncSession, actor: Actor, space_id: uuid.UUID, agent_id: uuid.UUID
    ) -> bool:
        if not await can(session, actor, Action.AI_USE):
            return False
        repo = AgentRepository(session, actor.org_id)
        agent = await repo.get(agent_id)
        if agent is None or agent.status == AgentStatus.DRAFT or not owned_by(agent, actor):
            return False
        role = (await repo.roles(agent_id)).get(space_id)
        return role is not None and role >= SPACE_ACTION_MIN_ROLE[Action.TICKET_EDIT]

    async def assigned(
        self, session: AsyncSession, actor: Actor, ticket: WorkItem, by: Authorship | None
    ) -> None:
        await triggers.on_assignment(session, actor, ticket, by)

    async def unassigned(
        self,
        session: AsyncSession,
        actor: Actor,
        ticket: WorkItem,
        former: uuid.UUID,
        by: Authorship | None,
    ) -> None:
        handing = by.run_id if by is not None else None
        for run_id in await RunRepository(session, actor.org_id).open_on_ticket(former, ticket.id):
            if run_id != handing:
                await control.request_cancel(session, actor.org_id, run_id, actor.principal.id)


register_agent_hooks(_Hooks())
register_assignee_hooks(_Assignees())
