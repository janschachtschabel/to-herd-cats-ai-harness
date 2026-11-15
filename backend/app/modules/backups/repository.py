"""The SQL of `backup_run`. A backup acts for the installation, not for a person:
its row belongs to the installation's organisation (there is one, `orgs/models.py`)."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.backups.models import BackupRun, BackupState, BackupTrigger
from app.modules.orgs.models import Organization


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

    async def latest(self, org_id: uuid.UUID, limit: int) -> list[BackupRun]:
        """Newest first."""
        stmt = (
            select(BackupRun)
            .where(BackupRun.org_id == org_id)
            .order_by(BackupRun.started_at.desc(), BackupRun.id.desc())
            .limit(limit)
        )
        return list((await self.session.scalars(stmt)).all())
