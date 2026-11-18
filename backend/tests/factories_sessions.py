"""Login sessions in tests: the clock their expiry, idle limit and last use are judged
at (`auth/timing.SESSION_CLOCK`), set to now."""

from collections.abc import AsyncIterator

import pytest

from app.core.models_base import utcnow
from app.modules.auth import timing
from tests.support.clock import SettableClock


@pytest.fixture
def session_time(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[SettableClock]:
    """The clock login sessions read, set to now."""
    clock = SettableClock(utcnow())
    monkeypatch.setattr(timing, "SESSION_CLOCK", clock)
    yield clock
