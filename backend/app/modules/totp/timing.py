"""The time TOTP codes and waiting sign-ins are judged at: the wall time, like a login
session's expiry, never the scheduling clock that the browser tests move ahead
(`core/clock.SYSTEM_CLOCK`); the code in a person's authenticator follows the wall
time. Tests set `TOTP_CLOCK` to a `SettableClock` (`totp_clock` reads it at each call)."""

from datetime import datetime

from app.core.clock import Clock
from app.core.models_base import utcnow


class WallClock:
    def now(self) -> datetime:
        return utcnow()


TOTP_CLOCK: Clock = WallClock()


def totp_clock() -> Clock:
    return TOTP_CLOCK
