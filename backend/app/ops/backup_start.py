"""How a backup begins, under the backup lock (`backup.py`, plan M9 decisions 7 and
11, task 13): the run's row, the dead runs and leftovers cleared away.

A new backup gets a `running` row of its own. An owner's request (`request`, trigger
`admin`) is taken up instead: it must still be `running` and younger than
REQUEST_GRACE, else `backup.request_gone`. Rows still `running` are runs whose process
died (whoever holds the lock knows no backup runs), except requests waiting for a
worker; they become `interrupted`. The hidden `.herd-*.part` files such backups left
in the backups directory go too. The owners hear of it (`backup.changed`).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.modules.backups.live import tell_managers
from app.modules.backups.models import BackupState, BackupTrigger
from app.modules.backups.repository import REQUEST_GRACE, BackupRunRepository

logger = logging.getLogger(__name__)

ARCHIVE_PREFIX = "herd-"
PART_SUFFIX = ".part"


@dataclass(frozen=True)
class Job:
    trigger: BackupTrigger
    clock: Clock
    request: uuid.UUID | None  # an owner's request to take up, or None: a new row


async def begin(
    session: AsyncSession, settings: Settings, job: Job, started: datetime
) -> tuple[uuid.UUID, uuid.UUID] | str:
    """The organisation and the run, or the code of a refusal."""
    runs = BackupRunRepository(session)
    if job.request is None:
        org_id = await runs.installation_org()
        if org_id is None:
            return "backup.no_organization"
    else:
        request = await runs.get(job.request)
        if (
            request is None
            or request.state != BackupState.RUNNING
            or request.trigger != BackupTrigger.ADMIN
            or request.started_at < started - REQUEST_GRACE
        ):
            return "backup.request_gone"
        org_id = request.org_id
    spare = started - REQUEST_GRACE  # requests waiting for a worker are not dead
    if dead := await runs.interrupt_running(started, spare_requests_since=spare):
        logger.warning("backup.interrupted_found", extra={"count": dead})
    if left := remove_leftovers(settings.backup_dir):
        logger.warning("backup.leftovers_removed", extra={"count": left})
    run_id = job.request or (await runs.start(org_id, job.trigger, started)).id
    await tell_managers(session, org_id, run_id)
    return org_id, run_id


def remove_leftovers(directory: Path) -> int:
    """Remove the hidden `.herd-*.part` files of backups that died midway (archive,
    sidecar and scratch dump); the number removed. Only while holding the backup lock:
    then no other backup is writing one."""
    if not directory.is_dir():
        return 0
    removed = 0
    for path in directory.glob(f".{ARCHIVE_PREFIX}*{PART_SUFFIX}"):
        if path.is_file() and not path.is_symlink():
            path.unlink(missing_ok=True)
            removed += 1
    return removed
