"""The SQL of `backup_run`. A backup acts for the installation, not for a person:
its row belongs to the installation's organisation (there is one, `orgs/models.py`)."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.modules.backups.models import BackupRun, BackupState, BackupTrigger, OffsiteState
from app.modules.orgs.models import Organization

# A backup holds this advisory lock on a connection of its own while it runs: whoever
# takes it knows no backup is running, so every `running` row is one whose process died.
BACKUP_LOCK = "herd.backup"
_KEY = func.hashtextextended(BACKUP_LOCK, 0)


async def hold_backup_lock(connection: AsyncConnection) -> bool:
    """Take the backup lock for the connection's session; False if a backup holds it."""
    return bool(await connection.scalar(select(func.pg_try_advisory_lock(_KEY))))


async def release_backup_lock(connection: AsyncConnection) -> None:
    await connection.scalar(select(func.pg_advisory_unlock(_KEY)))


@dataclass(frozen=True)
class BackupFigures:
    last_ok: datetime | None
    last_failed: datetime | None
    last_bytes: int | None
    offsite_ok: datetime | None
    offsite_failed: datetime | None


class BackupRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def installation_org(self) -> uuid.UUID | None:
        """The installation's organisation (the oldest, should there be several)."""
        return await self.session.scalar(select(Organization.id).order_by(Organization.id).limit(1))

    async def start(self, org_id: uuid.UUID, trigger: BackupTrigger, at: datetime) -> BackupRun:
        run = BackupRun(org_id=org_id, trigger=trigger, state=BackupState.RUNNING, started_at=at)
        self.session.add(run)
        await self.session.flush()
        return run

    async def finish(
        self,
        run_id: uuid.UUID,
        *,
        state: BackupState,
        at: datetime,
        archive: str | None = None,
        size: int | None = None,
        archive_sha256: str | None = None,
        error_code: str | None = None,
    ) -> None:
        await self.session.execute(
            update(BackupRun)
            .where(BackupRun.id == run_id)
            .values(
                state=state,
                finished_at=at,
                archive=archive,
                bytes=size,
                archive_sha256=archive_sha256,
                error_code=error_code,
            )
        )

    async def set_offsite(self, run_id: uuid.UUID, state: OffsiteState) -> None:
        await self.session.execute(
            update(BackupRun).where(BackupRun.id == run_id).values(offsite_state=state)
        )

    async def figures(self) -> BackupFigures:
        """For the gauges, over every organisation (there is one): the last finish of a
        good and of a failed backup, the size of the last good one, the last finish of
        a good backup whose offsite push worked and of one whose push failed."""
        ok = BackupRun.state == BackupState.OK
        last_ok = await self.session.scalar(select(func.max(BackupRun.finished_at)).where(ok))
        last_failed = await self.session.scalar(
            select(func.max(BackupRun.finished_at)).where(BackupRun.state == BackupState.FAILED)
        )
        size = await self.session.scalar(
            select(BackupRun.bytes)
            .where(ok)
            .order_by(BackupRun.finished_at.desc(), BackupRun.id.desc())
            .limit(1)
        )
        offsite: dict[OffsiteState, datetime | None] = {}
        for state in (OffsiteState.OK, OffsiteState.FAILED):
            offsite[state] = await self.session.scalar(
                select(func.max(BackupRun.finished_at)).where(ok, BackupRun.offsite_state == state)
            )
        return BackupFigures(
            last_ok, last_failed, size, offsite[OffsiteState.OK], offsite[OffsiteState.FAILED]
        )

    async def interrupt_running(self, at: datetime) -> int:
        """Runs still `running` whose process is gone (after a restore, or seen by
        whoever holds the backup lock); how many."""
        result = await self.session.execute(
            update(BackupRun)
            .where(BackupRun.state == BackupState.RUNNING)
            .values(state=BackupState.INTERRUPTED, finished_at=at)
        )
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def interrupt_dead(self, at: datetime) -> int:
        """`interrupt_running` if no backup is running (the lock, for this
        transaction); how many."""
        if not await self.session.scalar(select(func.pg_try_advisory_xact_lock(_KEY))):
            return 0
        return await self.interrupt_running(at)

    async def latest(self, org_id: uuid.UUID, limit: int) -> list[BackupRun]:
        """Newest first."""
        stmt = (
            select(BackupRun)
            .where(BackupRun.org_id == org_id)
            .order_by(BackupRun.started_at.desc(), BackupRun.id.desc())
            .limit(limit)
        )
        return list((await self.session.scalars(stmt)).all())


async def clear_tables(session: AsyncSession, names: Iterable[str]) -> None:
    """Delete every row of the tables (fixed names from code, never input)."""
    for name in names:
        await session.execute(text(f'DELETE FROM "{name}"'))  # noqa: S608
