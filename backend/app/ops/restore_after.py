"""What follows a restore, in one transaction (plan M9 decision 6, spec 12.6): every
session and every open sign-in flow is gone (nobody stays signed in across a
restore), backups that were running in the archive's snapshot (the archive's own
run among them: rows started at or before the archive's `created_at`, which keeps
whole seconds) become `interrupted` with `backup.in_restored_archive`, which the
failure gauge does not count, and the restore is audited as `backup.restored` by
`system`. A `running` row that started later is a backup's on the restored database:
it is left to whoever holds the backup lock next.

CLEARED_AFTER_RESTORE names the tables emptied; a module that adds such state (OIDC
flows, collab grants) adds its table here, and a test checks that each exists.
"""

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.modules.audit.recorder import record_system
from app.modules.backups.repository import (
    IN_RESTORED_ARCHIVE,
    BackupRunRepository,
    clear_tables,
)

# `collab_grant` first: emptying `user_session` would only make its grants powerless.
CLEARED_AFTER_RESTORE: tuple[str, ...] = (
    "collab_grant",
    "oidc_flow",
    "user_session",
    "oauth_flow",
)


async def finish_restore(
    session: AsyncSession,
    *,
    archive_name: str,
    archive_created_at: datetime,
    revision_from: str,
    revision_to: str,
    clock: Clock,
) -> None:
    await clear_tables(session, CLEARED_AFTER_RESTORE)
    runs = BackupRunRepository(session)
    await runs.interrupt_running(
        clock.now(),
        code=IN_RESTORED_ARCHIVE,
        started_before=archive_created_at + timedelta(seconds=1),
    )
    org_id = await runs.installation_org()
    if org_id is None:
        return
    details = {"archive": archive_name, "revision_from": revision_from, "revision_to": revision_to}
    await record_system(session, org_id, "backup.restored", "organization", org_id, details)
