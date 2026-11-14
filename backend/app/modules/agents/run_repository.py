"""The SQL of runs as people see them: start one for a message, read one and its
events. What the worker does with runs is in `executor_repository.py`."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.agents.models import Agent, Run, RunEvent, RunState


class RunRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def enqueue(
        self,
        agent_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> uuid.UUID:
        """A queued run for the conversation: a new one, or the one already waiting
        (it will see this message too, since it reads the conversation when it starts).
        Safe under concurrent messages: the conversation has one queued run at most; one
        that a worker takes between our insert and our look is no longer waiting, and
        the next round queues a new one."""
        while True:
            found = await self._enqueue_once(agent_id, user_id, conversation_id, message_id)
            if found is not None:
                return found

    async def _enqueue_once(
        self,
        agent_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> uuid.UUID | None:
        stmt = (
            insert(Run)
            .values(
                org_id=self.org_id,
                agent_id=agent_id,
                user_id=user_id,
                conversation_id=conversation_id,
                trigger_message_id=message_id,
                state=RunState.QUEUED,
                attempt=0,
                steps=0,
                created_at=utcnow(),
            )
            .on_conflict_do_nothing(
                index_elements=["conversation_id"], index_where=text("state = 'queued'")
            )
            .returning(Run.id)
        )
        created = await self.session.scalar(stmt)
        if created is not None:
            return created
        return await self.session.scalar(
            select(Run.id).where(
                Run.org_id == self.org_id,
                Run.conversation_id == conversation_id,
                Run.state == RunState.QUEUED,
            )
        )

    async def waiting(self, conversation_id: uuid.UUID) -> bool:
        """Whether the conversation's run waits for a person's answer."""
        stmt = select(Run.id).where(
            Run.org_id == self.org_id,
            Run.conversation_id == conversation_id,
            Run.state == RunState.WAITING,
        )
        return await self.session.scalar(stmt) is not None

    async def get(self, run_id: uuid.UUID) -> tuple[Run, Agent] | None:
        stmt = (
            select(Run, Agent)
            .join(Agent, Agent.id == Run.agent_id)
            .where(Run.org_id == self.org_id, Run.id == run_id)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        return (row[0], row[1]) if row is not None else None

    async def events(
        self, run_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[RunEvent]:
        stmt = (
            select(RunEvent)
            .where(RunEvent.org_id == self.org_id, RunEvent.run_id == run_id)
            .order_by(RunEvent.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(RunEvent.id > after)
        return list((await self.session.scalars(stmt)).all())
