"""The run gauges' SQL (`worker/runs.py`), across organisations: nothing in it is
shown to anyone but the metrics."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.agents.models import MAX_RUNTIME_SECONDS, Run, RunState

STUCK_GRACE_SECONDS = 60


@dataclass(frozen=True, slots=True)
class OpenRuns:
    queued: int
    oldest_queued: float
    stuck: int
    waiting: int


async def open_runs(session: AsyncSession) -> OpenRuns:
    """For the gauges, across organisations: queued runs, the age of the oldest one
    (seconds, 0 without one), stuck runs (running with a lease that ran out, no worker
    took them up again, or for longer than any run may) and waiting runs."""
    now = utcnow()
    queued = select(func.count(), func.min(Run.created_at)).where(Run.state == RunState.QUEUED)
    count, oldest = (await session.execute(queued)).one()
    overdue = now - timedelta(seconds=MAX_RUNTIME_SECONDS + STUCK_GRACE_SECONDS)
    stuck = await session.scalar(
        select(func.count()).where(
            Run.state == RunState.RUNNING,
            or_(Run.lease_until < now, Run.started_at < overdue),
        )
    )
    waiting = await session.scalar(select(func.count()).where(Run.state == RunState.WAITING))
    age = (now - oldest).total_seconds() if oldest is not None else 0.0
    return OpenRuns(int(count), max(age, 0.0), int(stuck or 0), int(waiting or 0))
