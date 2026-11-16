"""The SQL of maintenance (`models.py`). Every change notifies `herd_maintenance` in
its transaction (no payload: each process reads the state again, `cache.py`)."""

import uuid
from datetime import datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.models import Maintenance, MaintenanceReason
from app.modules.maintenance.state import INACTIVE, MaintenanceState

CHANNEL = "herd_maintenance"


def stay_on_sql(at: datetime) -> str:
    """SQL that turns maintenance on for every organisation of whatever database it
    runs in, if that database has the table yet (an archive of an older release has
    not; then the processes keep the state they knew, `cache.py`). For the restore's
    own transaction (`ops/replace.py`): names are schema-qualified, because
    pg_restore's script empties the search path. `at` is a time this code made."""
    started = at.isoformat()
    reason = MaintenanceReason.RESTORE.value
    # No input reaches this text: a constant and a time made here.
    return (
        "DO $herd$ BEGIN\n"  # noqa: S608
        "  IF pg_catalog.to_regclass('public.maintenance') IS NOT NULL THEN\n"
        "    INSERT INTO public.maintenance (id, org_id, active, reason, started_at, version)\n"
        f"    SELECT pg_catalog.gen_random_uuid(), o.id, true, '{reason}',"
        f" '{started}'::timestamptz, 1\n"
        "    FROM public.organization o\n"
        "    ON CONFLICT (org_id) DO UPDATE SET active = true,"
        " reason = excluded.reason, started_at = excluded.started_at,"
        " version = public.maintenance.version + 1;\n"
        "  END IF;\n"
        "END $herd$;\n"
    )


class MaintenanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current(self) -> MaintenanceState:
        """The installation's state: active if any organisation's row is (there is
        one organisation; a restore replaces the whole database)."""
        row = (
            await self.session.execute(
                select(Maintenance.reason, Maintenance.started_at)
                .where(Maintenance.active)
                .order_by(Maintenance.started_at)
                .limit(1)
            )
        ).first()
        if row is None:
            return INACTIVE
        return MaintenanceState(True, MaintenanceReason(row.reason), row.started_at)

    async def row(self, org_id: uuid.UUID) -> Maintenance | None:
        return await self.session.scalar(select(Maintenance).where(Maintenance.org_id == org_id))

    async def turn_on(self, org_id: uuid.UUID, reason: MaintenanceReason, at: datetime) -> int:
        """Active from `at` for `reason`; the new version."""
        values = insert(Maintenance).values(
            org_id=org_id, active=True, reason=reason, started_at=at, version=1
        )
        stmt = values.on_conflict_do_update(
            index_elements=[Maintenance.org_id],
            set_={
                "active": True,
                "reason": values.excluded.reason,
                "started_at": values.excluded.started_at,
                "version": Maintenance.version + 1,
            },
        ).returning(Maintenance.version)
        version = int((await self.session.execute(stmt)).scalar_one())
        await self.notify()
        return version

    async def turn_off(self, org_id: uuid.UUID, version: int | None) -> int:
        """Inactive, if active (and at `version`, when given); how many rows."""
        stmt = (
            update(Maintenance)
            .where(Maintenance.org_id == org_id, Maintenance.active)
            .values(active=False, reason=None, started_at=None, version=Maintenance.version + 1)
        )
        if version is not None:
            stmt = stmt.where(Maintenance.version == version)
        changed = int((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]
        if changed:
            await self.notify()
        return changed

    async def notify(self) -> None:
        await self.session.execute(select(func.pg_notify(CHANNEL, "")))

    async def stay_on(self, at: datetime) -> None:
        """`stay_on_sql` in this session's transaction (after a restore's migration)."""
        await self.session.execute(text(stay_on_sql(at)))
