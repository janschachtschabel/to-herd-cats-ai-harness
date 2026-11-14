"""The time as code that schedules sees it: `Clock.now()`, aware, in UTC. The worker
uses `SYSTEM_CLOCK`; tests pass a clock they set (`tests/support/clock.py`), so they
never sleep to let a term come due."""

from datetime import datetime
from typing import Protocol

from app.core.models_base import utcnow


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return utcnow()


SYSTEM_CLOCK = SystemClock()
