"""What a process knows about maintenance (`cache.py`): a value, no database."""

from dataclasses import dataclass
from datetime import datetime

from app.modules.maintenance.models import MaintenanceReason


@dataclass(frozen=True, slots=True)
class MaintenanceState:
    active: bool
    reason: MaintenanceReason | None = None
    started_at: datetime | None = None


INACTIVE = MaintenanceState(active=False)
