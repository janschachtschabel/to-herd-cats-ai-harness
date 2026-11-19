"""Telling the people who manage backups that one changed (plan M9 task 13): one
`backup.changed` per active person with `backup.manage` (owners), with the run's id
and nothing else, so their administration page reloads its lists.

Not an outbox event: backups are written by processes that may run without a worker
(the command line, the chart's CronJob) and act as `system`, which no event actor
names. The NOTIFY goes out on `herd_live` in the caller's transaction, so Postgres
sends it when that commits (never for a rolled-back one); every API process's hub
(`messaging/live.py`) hands it to that person's streams while their session is valid.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.backups.repository import BackupRunRepository
from app.modules.messaging.live_events import BACKUP, LIVE_CHANNEL, LiveEvent


async def tell_managers(
    session: AsyncSession, org_id: uuid.UUID, backup_id: uuid.UUID | None
) -> None:
    for user_id in await BackupRunRepository(session).managers(org_id):
        event = LiveEvent(
            name=BACKUP,
            org_id=org_id,
            conversation_id=None,
            message_id=None,
            parent_id=None,
            user_id=user_id,
            backup_id=backup_id,
        )
        await session.execute(select(func.pg_notify(LIVE_CHANNEL, event.payload())))
