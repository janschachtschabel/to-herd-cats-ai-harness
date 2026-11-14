"""The SQL of the run executor (`executor.py`): claiming runs, keeping their lease,
the steps' records, and the end (what a run reads: `read_repository.py`).

Claiming is the worker's, across organisations (like the outbox dispatcher; nothing in
it is shown to anyone); everything after is scoped by the run's organisation.

- A run is claimed when it is queued and its lane (`models.LANE`: a channel
  thread, else the conversation) has no active run (running or waiting), or when
  it is running and its lease has run out (its worker died: it is
  taken up again and goes on from its journal, `recoveries` + 1). Every take-up counts
  in `attempt` and sets `taken_at`; `started_at` stays that of the first. A
  connection's running runs (with a live lease) stay below its `max_concurrency`. Claims take a
  transaction-level advisory lock, so two workers never count the same free place
  twice; `SKIP LOCKED` passes over rows a finishing run holds.
- Every write of a step checks first that the run is still this attempt's
  (`owned`: the row locked, state `running`, the same attempt). A worker that lost its
  lease finds out there and stops without writing anything.
- Renewing passes over the rows it finds locked (`SKIP LOCKED`, a materialized CTE):
  a step of this worker holds its run's row for as long as its tool takes, and one
  renewal statement waiting on it would renew none of the worker's runs. Such a run
  counts as kept while it is still this attempt's (it is alive: inside its step,
  which no claim can take from it); the step sets its lease when it commits (`keep`).
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, exists, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.models_base import utcnow
from app.core.principal import PrincipalType
from app.core.repository import limit_time, locked_batch
from app.modules.agents.models import (
    Agent,
    EventKind,
    RateWindow,
    Run,
    RunEvent,
    RunState,
)
from app.modules.ai.models import AiConnection
from app.modules.messaging.models import Conversation, Message, MessageKind

CLAIM_LOCK = 0x4845_5244_5255_4E53 & 0x7FFF_FFFF_FFFF_FFFF  # "HERDRUNS"
RATE_WINDOW = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class Claimed:
    id: uuid.UUID
    org_id: uuid.UUID
    agent_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    attempt: int
    started_at: datetime
    recoveries: int = 0
    trigger_message_id: uuid.UUID | None = None  # None: a ticket's run
    work_item_id: uuid.UUID | None = None
    chain_depth: int = 0
    lease: float = 0.0  # seconds a step's commit extends the lease by (0: none)

    @classmethod
    def of(cls, run: Run, lease: float = 0.0) -> "Claimed":
        """The run as its current take-up holds it (without `lease`: for ending one
        nobody works on)."""
        return cls(
            run.id,
            run.org_id,
            run.agent_id,
            run.user_id,
            run.conversation_id,
            run.attempt,
            run.started_at or run.created_at,
            run.recoveries,
            run.trigger_message_id,
            run.work_item_id,
            run.chain_depth,
            lease,
        )


async def claim(session: AsyncSession, lease: float) -> Claimed | None:
    """The next run to work on, now this worker's (the caller commits)."""
    await session.execute(select(func.pg_advisory_xact_lock(CLAIM_LOCK)))
    now = utcnow()
    other = aliased(Run)
    busy = exists().where(
        func.coalesce(other.lane_id, other.conversation_id)
        == func.coalesce(Run.lane_id, Run.conversation_id),
        other.state.in_((RunState.RUNNING, RunState.WAITING)),
    )
    mine = aliased(Run)
    theirs = aliased(Agent)
    running_here = (
        select(func.count())
        .select_from(mine)
        .join(theirs, theirs.id == mine.agent_id)
        .where(
            theirs.connection_id == Agent.connection_id,
            mine.state == RunState.RUNNING,
            mine.lease_until >= now,
        )
        .scalar_subquery()
    )
    stmt = (
        select(Run)
        .join(Agent, Agent.id == Run.agent_id)
        .join(AiConnection, AiConnection.id == Agent.connection_id)
        .where(
            or_(
                and_(Run.state == RunState.QUEUED, ~busy),
                and_(Run.state == RunState.RUNNING, Run.lease_until < now),
            ),
            running_here < AiConnection.max_concurrency,
        )
        .order_by(Run.created_at, Run.id)
        .limit(1)
        .with_for_update(of=Run, skip_locked=True, key_share=False)
    )
    run = await session.scalar(stmt)
    if run is None:
        return None
    if run.state == RunState.RUNNING:
        run.recoveries += 1  # its worker died
    run.state = RunState.RUNNING
    run.attempt += 1
    run.started_at = run.started_at or now
    run.taken_at = now
    run.lease_until = now + timedelta(seconds=lease)
    await session.flush()
    return Claimed.of(run, lease)


async def renew(session: AsyncSession, held: dict[uuid.UUID, int], lease: float) -> set[uuid.UUID]:
    """A new lease for the runs this worker holds (id → attempt) whose rows are free;
    the ids still its, those a step holds locked included."""
    if not held:
        return set()
    pairs = [and_(Run.id == run_id, Run.attempt == attempt) for run_id, attempt in held.items()]
    ours = and_(Run.state == RunState.RUNNING, or_(*pairs))
    free = locked_batch(select(Run.id).where(ours).with_for_update(skip_locked=True), "free")
    until = utcnow() + timedelta(seconds=lease)
    await session.execute(update(Run).where(Run.id == free.c.id).values(lease_until=until))
    return set(await session.scalars(select(Run.id).where(ours)))


class RunSteps:
    """One run's records, in the run's organisation, for one attempt."""

    def __init__(self, session: AsyncSession, run: Claimed) -> None:
        self.session = session
        self.run = run

    async def owned(self) -> Run | None:
        """The run, locked, if it is still this attempt's."""
        stmt = (
            select(Run)
            .where(
                Run.org_id == self.run.org_id,
                Run.id == self.run.id,
                Run.attempt == self.run.attempt,
                Run.state == RunState.RUNNING,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    def keep(self, run: Run) -> None:
        """The step commits: the run's lease runs from now (the renewal passes over a
        row its step holds)."""
        if self.run.lease > 0:
            run.lease_until = utcnow() + timedelta(seconds=self.run.lease)

    async def limit_time(self, lock_seconds: float, statement_seconds: float) -> None:
        """The step's lock waits and statements end after so long (`db_errors`)."""
        await limit_time(self.session, int(lock_seconds * 1000), int(statement_seconds * 1000))

    async def event(self, seq: int, kind: EventKind, content: Mapping[str, object]) -> None:
        """The step's event; a second write of the same step fails (unique)."""
        self.session.add(
            RunEvent(
                org_id=self.run.org_id,
                run_id=self.run.id,
                attempt=self.run.attempt,
                seq=seq,
                kind=kind,
                content=dict(content),
                created_at=utcnow(),
            )
        )
        await self.session.flush()

    async def journal(self) -> list[RunEvent]:
        """The run's model and tool calls so far, in the order they were recorded."""
        stmt = (
            select(RunEvent)
            .where(
                RunEvent.org_id == self.run.org_id,
                RunEvent.run_id == self.run.id,
                RunEvent.kind != EventKind.STOP,
            )
            .order_by(RunEvent.seq, RunEvent.attempt)
        )
        return list((await self.session.scalars(stmt)).all())

    async def wait(self, run: Run, until: datetime) -> None:
        """The run waits for a person, holding nothing (no lease)."""
        run.state = RunState.WAITING
        run.lease_until = None
        run.wait_until = until
        await self.session.flush()

    async def agent(self) -> Agent | None:
        stmt = select(Agent).where(Agent.org_id == self.run.org_id, Agent.id == self.run.agent_id)
        return await self.session.scalar(stmt.execution_options(populate_existing=True))

    async def connection(self, connection_id: uuid.UUID) -> AiConnection | None:
        stmt = select(AiConnection).where(
            AiConnection.org_id == self.run.org_id, AiConnection.id == connection_id
        )
        return await self.session.scalar(stmt.execution_options(populate_existing=True))

    async def take_rate(self, connection_id: uuid.UUID, per_minute: int) -> float:
        """A place in the connection's `requests_per_minute` (0.0), or the seconds until
        its window ends (nothing taken)."""
        now = utcnow()
        fresh = RateWindow.window_start <= now - RATE_WINDOW
        stmt = (
            insert(RateWindow)
            .values(org_id=self.run.org_id, connection_id=connection_id, window_start=now, calls=1)
            .on_conflict_do_update(
                index_elements=[RateWindow.connection_id],
                set_={
                    "window_start": text(
                        "CASE WHEN ai_rate_window.window_start <= :cut THEN :now "
                        "ELSE ai_rate_window.window_start END"
                    ).bindparams(cut=now - RATE_WINDOW, now=now),
                    "calls": text(
                        "CASE WHEN ai_rate_window.window_start <= :cut THEN 1 "
                        "ELSE ai_rate_window.calls + 1 END"
                    ).bindparams(cut=now - RATE_WINDOW),
                },
                where=or_(fresh, RateWindow.calls < per_minute),
            )
            .returning(RateWindow.connection_id)
        )
        if await self.session.scalar(stmt) is not None:
            return 0.0
        start = await self.session.scalar(
            select(RateWindow.window_start).where(RateWindow.connection_id == connection_id)
        )
        if start is None:
            return 0.0
        return max((start + RATE_WINDOW - now).total_seconds(), 0.05)

    async def answer(self, text_md: str, parent: Message | None) -> Message | None:
        """The agent's answer, once per run (`client_id` = the run; None if written);
        with `parent`: a reply in its thread (the caller counts it)."""
        stmt = (
            insert(Message)
            .values(
                org_id=self.run.org_id,
                conversation_id=self.run.conversation_id,
                parent_id=parent.id if parent is not None else None,
                author_type=PrincipalType.AGENT,
                author_id=self.run.agent_id,
                kind=MessageKind.AGENT,
                body_md=text_md,
                client_id=self.run.id,
                run_id=self.run.id,
                created_at=utcnow(),
            )
            .on_conflict_do_nothing(index_elements=["author_id", "client_id"])
            .returning(Message)
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def conversation(self) -> Conversation:
        stmt = select(Conversation).where(
            Conversation.org_id == self.run.org_id, Conversation.id == self.run.conversation_id
        )
        return (await self.session.scalars(stmt)).one()

    async def done(self, run: Run, reason: str) -> None:
        run.state = RunState.DONE
        run.stop_reason = reason  # type: ignore[assignment]
        run.lease_until = None
        run.wait_until = None
        run.finished_at = utcnow()
        await self.session.flush()
