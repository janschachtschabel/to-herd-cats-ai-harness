"""The time login sessions are judged at (expiry, idle limit, last use): the wall time,
never the scheduling clock that the browser tests move ahead (`core/clock.SYSTEM_CLOCK`).
Tests set `SESSION_CLOCK` to a `SettableClock` (`session_clock` reads it at each call)."""

from app.core.clock import Clock
from app.modules.totp.timing import WallClock

SESSION_CLOCK: Clock = WallClock()


def session_clock() -> Clock:
    return SESSION_CLOCK
