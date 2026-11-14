"""What messaging asks of agents (`messaging/agent_hooks.py`), registered on import
(by the agent routes and the worker's handlers; not by the package, whose models the
core's repositories import).

A new top-level message of the person in a DM with an agent queues a run in the
message's own transaction, if the person and the agent may (`standing.refusal`);
otherwise the message stays without one and the answer says why. Replies in a thread
start nothing, and so does a message while the conversation's run waits for a
person's answer (`run.waiting`: that run answers first, and when it ends it queues a
run for what came meanwhile).
"""

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.principal import PrincipalType
from app.modules.agents.repository import AgentRepository
from app.modules.agents.run_repository import RunRepository
from app.modules.agents.standing import Refusal, refusal, visible_agent
from app.modules.messaging.agent_hooks import RunStart, register_agent_hooks
from app.modules.messaging.models import Conversation, ConversationKind, Message


class _Hooks:
    async def require_addressable(
        self, session: AsyncSession, actor: Actor, agent_id: uuid.UUID
    ) -> None:
        await visible_agent(session, actor, agent_id)

    async def after_post(
        self, session: AsyncSession, actor: Actor, conversation: Conversation, message: Message
    ) -> RunStart | None:
        if conversation.kind != ConversationKind.DM or actor.principal.type != PrincipalType.USER:
            return None
        agent = await AgentRepository(session, actor.org_id).of_conversation(conversation.id)
        if agent is None:
            return None
        if message.parent_id is not None:
            return RunStart(None, Refusal.THREAD_REPLY.value)
        why = await refusal(session, actor, agent)
        if why is not None:
            return RunStart(None, why.value)
        runs = RunRepository(session, actor.org_id)
        if await runs.waiting(conversation.id):
            return RunStart(None, Refusal.RUN_WAITING.value)
        run_id = await runs.enqueue(agent.id, actor.principal.id, conversation.id, message.id)
        return RunStart(run_id, None)

    async def names(
        self, session: AsyncSession, org_id: uuid.UUID, ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        return await AgentRepository(session, org_id).names(set(ids))


register_agent_hooks(_Hooks())
