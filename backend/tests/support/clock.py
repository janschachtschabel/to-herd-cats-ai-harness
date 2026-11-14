"""A clock a test sets and moves (`app.core.clock.Clock`)."""

from datetime import UTC, datetime, timedelta


class SettableClock:
    def __init__(self, at: datetime) -> None:
        self.at = at.astimezone(UTC)

    def now(self) -> datetime:
        return self.at

    def set(self, at: datetime) -> None:
        self.at = at.astimezone(UTC)

    def advance(self, by: timedelta) -> None:
        self.at += by
