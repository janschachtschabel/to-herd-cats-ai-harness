"""Automation rows for tests (the management API comes with plan M7 task 7)."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Run, RunState, StopReason
from app.modules.automations.models import (
    Automation,
    AutomationFiring,
    AutomationKind,
    AutomationState,
    PausedReason,
)

HOURLY = "0 * * * *"


def automation_row(
    org_id: object,
    owner_id: object,
    agent_id: object,
    conversation_id: object,
    *,
    due: datetime,
    cron: str | None = HOURLY,
    time_zone: str = "Europe/Berlin",
    paused: bool = False,
) -> Automation:
    """A recurring automation (`cron`), or a `once` (`cron=None`), due at `due`."""
    return Automation(
        org_id=org_id,
        owner_user_id=owner_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        instruction="Summarise what happened.",
        kind=AutomationKind.RECURRING if cron else AutomationKind.ONCE,
        cron=cron,
        time_zone=time_zone if cron else None,
        next_due_at=due,
        state=AutomationState.PAUSED if paused else AutomationState.ACTIVE,
        paused_reason=PausedReason.MANUAL if paused else None,
    )


async def firings(session: AsyncSession, automation_id: uuid.UUID) -> list[AutomationFiring]:
    stmt = (
        select(AutomationFiring)
        .where(AutomationFiring.automation_id == automation_id)
        .order_by(AutomationFiring.due_at)
        .execution_options(populate_existing=True)
    )
    return list((await session.scalars(stmt)).all())


async def runs_of(session: AsyncSession, automation_id: uuid.UUID) -> list[Run]:
    stmt = (
        select(Run)
        .where(Run.automation_id == automation_id)
        .order_by(Run.created_at)
        .execution_options(populate_existing=True)
    )
    return list((await session.scalars(stmt)).all())


async def reload(session: AsyncSession, automation_id: uuid.UUID) -> Automation:
    stmt = (
        select(Automation)
        .where(Automation.id == automation_id)
        .execution_options(populate_existing=True)
    )
    found = await session.scalar(stmt)
    assert found is not None
    return found


async def finish_runs(session: AsyncSession) -> None:
    """Every open run ends `completed` (as if a worker had answered it)."""
    await session.execute(
        update(Run)
        .where(Run.state != RunState.DONE)
        .values(
            state=RunState.DONE,
            stop_reason=StopReason.COMPLETED,
            lease_until=None,
            wait_until=None,
        )
    )
