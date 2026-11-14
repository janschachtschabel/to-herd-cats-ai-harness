"""The SQL of steering runs from outside their worker (`control.py`): cancel
requests, resuming a waiting run, the waiting runs that are due, and the question a
finished run leaves unanswered. Scoped by the organisation, except `due_waiting`,
which is the worker's, across organisations (like claiming)."""

import uuid
from datetime import datetime

from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db_errors import is_timeout
from app.core.errors import RetryConflict
from app.core.principal import PrincipalType
from app.modules.agents.models import Run, RunState
from app.modules.agents.run_control_models import RunCancelRequest
from app.modules.messaging.models import Message, MessageKind


class ControlRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def lock(self, run_id: uuid.UUID) -> Run | None:
        stmt = (
            select(Run)
            .where(Run.org_id == self.org_id, Run.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def lock_briefly(self, run_id: uuid.UUID, wait_seconds: float) -> Run | None:
        """The run's row locked `FOR NO KEY UPDATE`, waiting at most `wait_seconds`
        (else `RetryConflict`); the transaction's lock bound is as before afterwards."""
        before = await self.session.scalar(select(func.current_setting("lock_timeout")))
        stmt = (
            select(Run)
            .where(Run.org_id == self.org_id, Run.id == run_id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        try:
            async with self.session.begin_nested():
                await self._lock_timeout(f"{max(1, int(wait_seconds * 1000))}ms")
                run = await self.session.scalar(stmt)
        except DBAPIError as exc:
            if not is_timeout(exc):
                raise
            raise RetryConflict("A run is working on it; send the request again.") from exc
        await self._lock_timeout(str(before))
        return run

    async def _lock_timeout(self, value: str) -> None:
        await self.session.execute(select(func.set_config("lock_timeout", value, True)))

    async def cancelled_by(self, run_id: uuid.UUID) -> uuid.UUID | None:
        """Who asked the run to stop, if anyone did."""
        stmt = select(RunCancelRequest.requested_by).where(
            RunCancelRequest.org_id == self.org_id, RunCancelRequest.run_id == run_id
        )
        return await self.session.scalar(stmt)

    async def add_cancel_request(self, run_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Once per run; a second request keeps the first."""
        stmt = (
            insert(RunCancelRequest)
            .values(org_id=self.org_id, run_id=run_id, requested_by=user_id)
            .on_conflict_do_nothing(index_elements=[RunCancelRequest.run_id])
        )
        await self.session.execute(stmt)

    async def drop_queued(self, run: Run) -> None:
        """A DM's queued run that never started, if one waits behind the run being
        resumed in its lane (what it would have answered, the follow-up answers). A
        ticket's run (a handover waiting behind the run that handed over) is kept."""
        await self.session.execute(
            delete(Run).where(
                Run.org_id == self.org_id,
                Run.conversation_id == run.conversation_id,
                Run.lane_id.is_not_distinct_from(run.lane_id),
                Run.work_item_id.is_(None),
                Run.state == RunState.QUEUED,
                Run.attempt == 0,
            )
        )

    async def unanswered(self, run: Run) -> uuid.UUID | None:
        """The newest top-level message of the run's person in its conversation, sent
        after the run started, if no run is queued for it there."""
        queued = exists().where(
            Run.org_id == self.org_id,
            Run.conversation_id == run.conversation_id,
            Run.state == RunState.QUEUED,
        )
        stmt = (
            select(Message.id)
            .where(
                Message.org_id == self.org_id,
                Message.conversation_id == run.conversation_id,
                Message.parent_id.is_(None),
                Message.deleted_at.is_(None),
                Message.kind == MessageKind.HUMAN,
                Message.author_type == PrincipalType.USER,
                Message.author_id == run.user_id,
                Message.created_at > (run.started_at or run.created_at),
                ~queued,
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)


async def due_waiting(session: AsyncSession, now: datetime, limit: int) -> list[Run]:
    """Waiting runs whose time ran out or that someone asked to stop, locked (rows
    another worker is ending are passed over)."""
    asked = exists().where(RunCancelRequest.run_id == Run.id)
    stmt = (
        select(Run)
        .where(Run.state == RunState.WAITING, or_(Run.wait_until <= now, asked))
        .order_by(Run.wait_until, Run.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list((await session.scalars(stmt)).all())
