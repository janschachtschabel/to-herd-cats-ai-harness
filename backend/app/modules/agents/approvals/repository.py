"""The SQL of approvals and questions (`models.py`), scoped by the organisation."""

import uuid
from typing import TypeVar

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.approvals.models import (
    Approval,
    ApprovalState,
    QuestionState,
    RunQuestion,
)
from app.modules.agents.models import Run

W = TypeVar("W", Approval, RunQuestion)


class WaitedRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def for_call(
        self, model: type[W], run_id: uuid.UUID, step: int, call_id: str
    ) -> W | None:
        stmt = select(model).where(
            model.org_id == self.org_id,
            model.run_id == run_id,
            model.step == step,
            model.call_id == call_id,
        )
        return await self.session.scalar(stmt.execution_options(populate_existing=True))

    async def get(self, model: type[W], id_: uuid.UUID, *, lock: bool = False) -> W | None:
        stmt = select(model).where(model.org_id == self.org_id, model.id == id_)
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt.execution_options(populate_existing=True))

    async def add(self, row: W) -> W:
        self.session.add(row)
        await self.session.flush()
        return row

    async def pending_approval(self, run_id: uuid.UUID) -> bool:
        stmt = select(Approval.id).where(
            Approval.org_id == self.org_id,
            Approval.run_id == run_id,
            Approval.state == ApprovalState.PENDING,
        )
        return await self.session.scalar(stmt.limit(1)) is not None

    async def expire_pending(self, run_id: uuid.UUID) -> None:
        """A run that ends leaves nothing open to decide or answer."""
        for model, pending, expired in (
            (Approval, ApprovalState.PENDING, ApprovalState.EXPIRED),
            (RunQuestion, QuestionState.PENDING, QuestionState.EXPIRED),
        ):
            await self.session.execute(
                update(model)
                .where(model.org_id == self.org_id, model.run_id == run_id, model.state == pending)
                .values(state=expired, version=model.version + 1)
                .execution_options(synchronize_session=False)
            )

    async def approvals_of(
        self,
        user_id: uuid.UUID,
        state: ApprovalState | None,
        before: uuid.UUID | None,
        limit: int,
    ) -> list[Approval]:
        """Those addressed to the person, newest first (ids are time-ordered)."""
        stmt = select(Approval).where(
            Approval.org_id == self.org_id, Approval.addressed_to == user_id
        )
        if state is not None:
            stmt = stmt.where(Approval.state == state)
        if before is not None:
            stmt = stmt.where(Approval.id < before)
        stmt = stmt.order_by(Approval.id.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def runs(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, Run]:
        if not ids:
            return {}
        stmt = select(Run).where(Run.org_id == self.org_id, Run.id.in_(ids))
        return {run.id: run for run in (await self.session.scalars(stmt)).all()}
