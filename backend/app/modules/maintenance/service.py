"""Turning maintenance on and off (plan M9 decision 9). The command line and the
restore act as `system` (audit `maintenance.started` / `maintenance.ended` with
`via`); a change against a version that moved on answers 409
`maintenance.version_conflict`."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict
from app.modules.audit.recorder import record_system
from app.modules.maintenance.models import Maintenance, MaintenanceReason
from app.modules.maintenance.repository import MaintenanceRepository
from app.modules.maintenance.state import MaintenanceState


class MaintenanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MaintenanceRepository(session)

    async def state(self) -> MaintenanceState:
        return await self.repo.current()

    async def row(self, org_id: uuid.UUID) -> Maintenance | None:
        return await self.repo.row(org_id)

    async def begin(
        self, org_id: uuid.UUID, reason: MaintenanceReason, at: datetime, *, via: str = "cli"
    ) -> int:
        """On from `at`; the new version."""
        version = await self.repo.turn_on(org_id, reason, at)
        details = {"reason": reason.value, "via": via}
        await record_system(
            self.session, org_id, "maintenance.started", "organization", org_id, details
        )
        return version

    async def end(self, org_id: uuid.UUID, *, version: int | None = None, via: str = "cli") -> bool:
        """Off; False when it was not on. With `version`, only from that version."""
        if not await self.repo.turn_off(org_id, version):
            row = await self.repo.row(org_id)
            if version is not None and row is not None and row.version != version:
                raise Conflict(
                    code="maintenance.version_conflict", details={"version": row.version}
                )
            return False
        await record_system(
            self.session, org_id, "maintenance.ended", "organization", org_id, {"via": via}
        )
        return True

    async def end_all(self, *, via: str = "cli") -> bool:
        """Off for every organisation (after a restore, whose archive brings its own);
        False when none was on."""
        ended = await self.repo.turn_off_all()
        for org_id in ended:
            await record_system(
                self.session, org_id, "maintenance.ended", "organization", org_id, {"via": via}
            )
        return bool(ended)
