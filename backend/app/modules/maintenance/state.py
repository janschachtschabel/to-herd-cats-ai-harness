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
# What a process holds from its start until its first good read (review M9b F7): it
# may have started while a restore holds the tables, so it counts as in maintenance.
UNKNOWN = MaintenanceState(active=True)
