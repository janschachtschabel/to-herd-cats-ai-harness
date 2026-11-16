"""`python -m app.ops maintenance status|off` (plan M9 task 12): the way out when a
replace stopped after the swap and left maintenance on (`docs/SICHERUNG.md`)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import Conflict
from app.modules.audit.models import AuditLog
from app.modules.maintenance.models import MaintenanceReason
from app.modules.maintenance.service import MaintenanceService
from app.ops.cli import run
from tests.real_db import RealDb
from tests.support.clock import SettableClock

AT = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)


def _printed(capsys: pytest.CaptureFixture[str]) -> str:
    out = capsys.readouterr().out.splitlines()
    return "\n".join(line for line in out if not line.startswith("{"))


async def test_maintenance_status_and_off(
    real_db: RealDb, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = get_settings().model_copy(update={"database_url": get_settings().test_database_url})
    clock = SettableClock(AT)
    assert await run(["maintenance", "status"], settings, clock) == 0
    assert _printed(capsys) == "off"
    async with real_db.database.session_factory() as session:
        await MaintenanceService(session).begin(real_db.org_id, MaintenanceReason.RESTORE, AT)
        await session.commit()
    assert await run(["maintenance", "status"], settings, clock) == 0
    assert _printed(capsys) == "on restore since 2026-11-16T03:00:00Z"
    assert await run(["maintenance", "off"], settings, clock) == 0
    assert _printed(capsys) == "off"
    assert await run(["maintenance", "off"], settings, clock) == 0
    assert _printed(capsys) == "off (was off)"
    async with real_db.database.session_factory() as session:
        actions = (
            await session.scalars(
                select(AuditLog.action)
                .where(AuditLog.action.like("maintenance.%"))
                .order_by(AuditLog.id)
            )
        ).all()
    assert actions == ["maintenance.started", "maintenance.ended"]


async def test_ending_from_a_stale_version_is_a_conflict(session, org) -> None:  # type: ignore[no-untyped-def]
    service = MaintenanceService(session)
    first = await service.begin(org.id, MaintenanceReason.RESTORE, AT)
    second = await service.begin(org.id, MaintenanceReason.RESTORE, AT)
    assert second == first + 1
    with pytest.raises(Conflict) as stale:
        await service.end(org.id, version=first)
    assert stale.value.code == "maintenance.version_conflict"
    assert stale.value.details == {"version": second}
    assert (await service.state()).active
    assert await service.end(org.id, version=second)
    assert not (await service.state()).active
    row = await service.row(org.id)
    assert row is not None and row.version == second + 1
    assert not await service.end(org.id)
