"""`GET /api/maintenance` (plan M9 decision 9): whether the installation is in
maintenance, for everyone (no session: a browser in maintenance has none that works),
from the process's cache. The one API route maintenance leaves open."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.maintenance.cache import maintenance_cache
from app.modules.maintenance.models import MaintenanceReason

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


class MaintenanceOut(BaseModel):
    active: bool
    reason: MaintenanceReason | None
    started_at: datetime | None


@router.get("", response_model=MaintenanceOut)
async def maintenance_state() -> MaintenanceOut:
    state = maintenance_cache().state
    return MaintenanceOut(active=state.active, reason=state.reason, started_at=state.started_at)
