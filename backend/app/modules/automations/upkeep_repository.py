"""The worker's SQL about automations as a whole, across organisations: the gauges
(`DueLoop.update_metrics`, counts only) and the log's retention (`DueLoop.cleanup`).
Nothing of it is shown to anyone."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import ColumnElement, Select, and_, delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import locked_batch
from app.modules.agents.models import Run, RunState
from app.modules.automations.event_models import AutomationEvent
from app.modules.automations.models import (
    Automation,
    AutomationFiring,
    AutomationState,
    PausedReason,
)


class UpkeepRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def due(self, now: datetime) -> tuple[int, datetime | None]:
        """How many active automations are due at `now`, and the oldest due term (the
        due loop's index, `ix_automation_due`)."""
        stmt = select(func.count(), func.min(Automation.next_due_at)).where(
            Automation.state == AutomationState.ACTIVE, Automation.next_due_at <= now
        )
        count, oldest = (await self.session.execute(stmt)).one()
        return int(count), oldest

    async def paused(self) -> dict[PausedReason, int]:
        """Paused automations by reason (every reason, 0 without one)."""
        stmt = (
            select(Automation.paused_reason, func.count())
            .where(Automation.state == AutomationState.PAUSED)
            .group_by(Automation.paused_reason)
        )
        rows = (await self.session.execute(stmt)).all()
        found = {PausedReason(str(r)): int(n) for r, n in rows}
        return {reason: found.get(reason, 0) for reason in PausedReason}

    # --- retention (`DueLoop.cleanup`) ------------------------------------------------

    async def delete_terms_before(self, cutoff: datetime, limit: int) -> int:
        """Up to `limit` terms fired before `cutoff` whose run has ended (or that
        started none), with the events they took (cascade); rows another worker is
        deleting are skipped (`ix_automation_firing_fired_at`)."""
        doomed = locked_batch(
            select(AutomationFiring.id)
            .where(AutomationFiring.fired_at < cutoff, _run_ended())
            .limit(limit)
            .with_for_update(of=AutomationFiring, skip_locked=True),
            "doomed_terms",
        )
        stmt = delete(AutomationFiring).where(AutomationFiring.id == doomed.c.id)
        return int((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]

    async def delete_events_taken_before(self, cutoff: datetime, limit: int) -> int:
        """Up to `limit` events taken by a term fired before `cutoff` whose run has
        ended (or that started none). An event still waiting for its quiet time's end
        has no term and is never among them."""
        rows = cast(Select[Any], select(AutomationEvent.automation_id, AutomationEvent.event_id))
        doomed = locked_batch(
            rows.join(AutomationFiring, AutomationFiring.id == AutomationEvent.firing_id)
            .where(AutomationFiring.fired_at < cutoff, _run_ended())
            .limit(limit)
            .with_for_update(of=AutomationEvent, skip_locked=True),
            "doomed_events",
        )
        stmt = delete(AutomationEvent).where(
            AutomationEvent.automation_id == doomed.c.automation_id,
            AutomationEvent.event_id == doomed.c.event_id,
        )
        return int((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]

    async def delete_waiting_of_idle_rules(self, cutoff: datetime, limit: int) -> int:
        """Up to `limit` events still waiting with a rule that will not fire them:
        a deleted one, or a paused one that took them in before `cutoff` (a paused
        rule takes in nothing new, so it has been paused about that long)."""
        rows = cast(Select[Any], select(AutomationEvent.automation_id, AutomationEvent.event_id))
        idle = or_(
            Automation.state == AutomationState.DELETED,
            and_(Automation.state == AutomationState.PAUSED, AutomationEvent.taken_at < cutoff),
        )
        doomed = locked_batch(
            rows.join(Automation, Automation.id == AutomationEvent.automation_id)
            .where(AutomationEvent.firing_id.is_(None), idle)
            .limit(limit)
            .with_for_update(of=AutomationEvent, skip_locked=True),
            "doomed_waiting",
        )
        stmt = delete(AutomationEvent).where(
            AutomationEvent.automation_id == doomed.c.automation_id,
            AutomationEvent.event_id == doomed.c.event_id,
        )
        return int((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]


def _run_ended() -> ColumnElement[bool]:
    """The term started no run, or its run is done: nothing reads the term (its
    instruction, its thread) or its events (the own-effect rule) any more."""
    open_run = (
        select(Run.id)
        .where(Run.id == AutomationFiring.run_id, Run.state != RunState.DONE)
        .correlate(AutomationFiring)
    )
    return or_(AutomationFiring.run_id.is_(None), ~exists(open_run))
