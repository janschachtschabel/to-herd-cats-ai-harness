"""One whole backup run (plan M9 decision 7): `python -m app.ops backup run` (the
chart's CronJob) and each term of `backup schedule` (the compose service).

Archive → read back and checked (`create_backup`) → only for a good one: retention on
the volume, then offsite with restic, its outcome recorded on the run. A failed
backup deletes nothing. The exit status is 0 only when the backup and (if on) the
offsite push worked; the run row says which part failed. An owner's request (plan M9
task 13, `run_id`) runs the same way, in a worker (`modules/backups/jobs.py`).
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import make_engine
from app.modules.backups.live import tell_managers
from app.modules.backups.models import BackupState, BackupTrigger, OffsiteState
from app.modules.backups.repository import BackupRunRepository
from app.ops.backup import create_backup
from app.ops.offsite import push_offsite
from app.ops.retention import KeepRule, apply_retention


@dataclass(frozen=True)
class RunOutcome:
    state: BackupState
    archive: Path | None
    offsite: OffsiteState
    error_code: str | None


def keep_rule(settings: Settings) -> KeepRule:
    return KeepRule(
        settings.backup_keep_daily, settings.backup_keep_weekly, settings.backup_keep_monthly
    )


async def run_backup(
    settings: Settings, clock: Clock, *, trigger: BackupTrigger, run_id: uuid.UUID | None = None
) -> RunOutcome:
    outcome = await create_backup(settings, trigger=trigger, clock=clock, run_id=run_id)
    if outcome.state != BackupState.OK or outcome.archive is None or outcome.run_id is None:
        return RunOutcome(outcome.state, None, OffsiteState.OFF, outcome.error_code)
    rule = keep_rule(settings)
    apply_retention(settings.backup_dir, rule)
    offsite = await push_offsite(settings, outcome.archive, rule, clock)
    engine = make_engine(settings.migrate_database(), settings=settings)
    try:
        async with async_sessionmaker(engine)() as session, session.begin():
            runs = BackupRunRepository(session)
            await runs.set_offsite(outcome.run_id, offsite)
            run = await runs.get(outcome.run_id)
            if run is not None:
                await tell_managers(session, run.org_id, run.id)
    finally:
        await engine.dispose()
    return RunOutcome(outcome.state, outcome.archive, offsite, None)
