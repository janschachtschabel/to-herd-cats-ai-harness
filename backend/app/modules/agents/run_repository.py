"""The SQL of runs as people see them: start one for a message, a mention, a
ticket or an automation, read one and its events. What the worker does with runs is
in `executor_repository.py`."""

import uuid

from sqlalchemy import exists, func, literal, select, text, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.models_base import utcnow
from app.modules.agents.models import Agent
from app.modules.agents.run_models import LANE, Run, RunEvent, RunState

QUEUED = text("state = 'queued'")


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
            .on_conflict_do_nothing(index_elements=[LANE, Run.agent_id], index_where=QUEUED)
            .returning(Run.id)
        )
        created = await self.session.scalar(stmt)
        if created is not None:
            return created
        return await self.session.scalar(
            select(Run.id).where(
                Run.org_id == self.org_id,
                Run.conversation_id == conversation_id,
                Run.lane_id.is_(None),
                Run.state == RunState.QUEUED,
            )
        )

    async def start(
        self,
        agent_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        message_id: uuid.UUID | None = None,
        work_item_id: uuid.UUID | None = None,
        chain_depth: int = 0,
        besides: uuid.UUID | None = None,
        lane_id: uuid.UUID | None = None,
        automation_id: uuid.UUID | None = None,
    ) -> uuid.UUID | None:
        """A new queued run for a mention, a ticket or an automation, if its lane
        (`lane_id`: a channel thread's root or the automation; else the conversation)
        has no run queued, running or waiting other than `besides` (the run handing a
        ticket over from there: the new run follows it). None: it has one; two at
        once: one wins, the unique index of queued runs keeps the other out."""
        values = {
            "id": uuid7(),  # like every id: lists page newest first by it
            "org_id": self.org_id,
            "agent_id": agent_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "trigger_message_id": message_id,
            "work_item_id": work_item_id,
            "chain_depth": chain_depth,
            "lane_id": lane_id,
            "automation_id": automation_id,
            "state": RunState.QUEUED.value,
            "attempt": 0,
            "steps": 0,
            "created_at": utcnow(),
        }
        busy = exists().where(
            Run.org_id == self.org_id,
            func.coalesce(Run.lane_id, Run.conversation_id) == (lane_id or conversation_id),
            Run.state != RunState.DONE,
            Run.id != besides if besides is not None else true(),
        )
        row = select(*(literal(v, Run.__table__.c[k].type) for k, v in values.items())).where(~busy)
        stmt = (
            insert(Run)
            .from_select(list(values), row)
            .on_conflict_do_nothing(index_elements=[LANE, Run.agent_id], index_where=QUEUED)
            .returning(Run.id)
        )
        return await self.session.scalar(stmt)

    async def open_on_ticket(self, agent_id: uuid.UUID, work_item_id: uuid.UUID) -> list[uuid.UUID]:
        """The agent's runs on the ticket (its assignment's, a handover's) not done."""
        stmt = select(Run.id).where(
            Run.org_id == self.org_id,
            Run.agent_id == agent_id,
            Run.work_item_id == work_item_id,
            Run.state != RunState.DONE,
        )
        return list(await self.session.scalars(stmt))

    async def handed_over(self, run_id: uuid.UUID) -> int:
        """How many tickets the run handed to agents (its `assign_ticket` results
        marked `handover`)."""
        key = RunEvent.content["attrs"]["key"].astext
        stmt = select(func.count(func.distinct(key))).where(
            RunEvent.org_id == self.org_id,
            RunEvent.run_id == run_id,
            RunEvent.content["name"].astext == "assign_ticket",
            RunEvent.content["attrs"]["handover"].astext == "agent",
        )
        return int(await self.session.scalar(stmt) or 0)

    async def of_run(self, run_id: uuid.UUID) -> Run | None:
        stmt = select(Run).where(Run.org_id == self.org_id, Run.id == run_id)
        return await self.session.scalar(stmt)

    async def waiting(self, conversation_id: uuid.UUID) -> bool:
        """Whether the DM's run waits for a person's answer."""
        stmt = select(Run.id).where(
            Run.org_id == self.org_id,
            Run.conversation_id == conversation_id,
            Run.lane_id.is_(None),
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
