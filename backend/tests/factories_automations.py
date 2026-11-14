"""Automation rows for tests (the management API comes with plan M7 task 7)."""

import uuid
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Run, RunState, StopReason
from app.modules.automations.firing import Fired, fire_next
from app.modules.automations.models import (
    Automation,
    AutomationFiring,
    AutomationKind,
    AutomationState,
    PausedReason,
)
from app.modules.messaging.notification_models import Notification
from tests.factories_agents import Bench

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
    instruction: str = "Summarise what happened.",
) -> Automation:
    """A recurring automation (`cron`), or a `once` (`cron=None`), due at `due`."""
    return Automation(
        org_id=org_id,
        owner_user_id=owner_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        instruction=instruction,
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


T0 = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)  # a Monday, 10:00 in Berlin


async def placed(
    bench: Bench,
    conversation_id: object,
    *,
    owner: str = "alice",
    due: datetime = T0,
    **fields: Any,
) -> Automation:
    """An automation of the bench's agent at the place, owned by `owner`."""
    person = bench.people.users[owner]
    row = automation_row(
        person.org_id, person.id, bench.agent.id, uuid.UUID(str(conversation_id)), due=due, **fields
    )
    bench.session.add(row)
    await bench.session.flush()
    return row


OFFICE_DAYS = [1, 2, 3, 4, 5]


async def beating(
    bench: Bench,
    conversation_id: object,
    *,
    owner: str = "alice",
    due: datetime = T0,
    every: int = 30,
    days: list[int] | None = None,
    hours: tuple[time, time] = (time(9), time(17)),
    time_zone: str = "Europe/Berlin",
    checklist: str = "Sieh nach, ob Tickets ohne Bearbeitung liegen.",
) -> Automation:
    """A heartbeat of the bench's agent at the place: every `every` minutes in the
    active hours (Monday to Friday, 09:00–17:00 in Berlin unless said), due at `due`."""
    person = bench.people.users[owner]
    row = Automation(
        org_id=person.org_id,
        owner_user_id=person.id,
        agent_id=bench.agent.id,
        conversation_id=uuid.UUID(str(conversation_id)),
        instruction=checklist,
        kind=AutomationKind.HEARTBEAT,
        time_zone=time_zone,
        interval_minutes=every,
        active_days=days or OFFICE_DAYS,
        active_from=hours[0],
        active_until=hours[1],
        next_due_at=due,
        state=AutomationState.ACTIVE,
    )
    bench.session.add(row)
    await bench.session.flush()
    return row


async def fire(bench: Bench, at: datetime = T0) -> Fired:
    fired = await fire_next(bench.session, at)
    assert fired is not None, "nothing was due"
    return fired


async def notified(session: AsyncSession, automation_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
    """The activity entries about the automation: (person, reason), by person."""
    stmt = select(Notification.user_id, Notification.reason).where(
        Notification.automation_id == automation_id
    )
    return sorted((u, str(r)) for u, r in await session.execute(stmt))
