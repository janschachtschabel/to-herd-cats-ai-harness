"""Backups on a schedule in a long-running process (plan M9 decision 7; the compose
service `backup`: `python -m app.ops backup schedule`). Kubernetes uses a CronJob with
`backup run` instead.

The next term follows HERD_BACKUP_SCHEDULE (cron, UTC) from the clock's time; the loop
looks at the clock every `tick_seconds` (tests set the clock instead of sleeping) and
runs one backup per term. A term missed while the process was down is not caught up:
the next one counts.
"""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime

from cronsim import CronSim

from app.core.clock import Clock
from app.core.config import Settings
from app.modules.backups.models import BackupTrigger
from app.ops.cli_run import run_backup

TICK_SECONDS = 30.0

Run = Callable[..., Awaitable[object]]


def next_due(schedule: str, after: datetime) -> datetime:
    """The first term of `schedule` (UTC) after `after`."""
    start = after.astimezone(UTC).replace(tzinfo=None)
    return next(CronSim(schedule, start)).replace(tzinfo=UTC)


async def run_schedule(
    settings: Settings,
    clock: Clock,
    *,
    stop: asyncio.Event,
    tick_seconds: float = TICK_SECONDS,
    run: Run = run_backup,
) -> None:
    due = next_due(settings.backup_schedule, clock.now())
    while not stop.is_set():
        now = clock.now()
        if now >= due:
            await run(settings, clock, trigger=BackupTrigger.SCHEDULE)
            due = next_due(settings.backup_schedule, max(clock.now(), due))
            continue
        wait = min(tick_seconds, (due - now).total_seconds())
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=max(wait, 0.0))
