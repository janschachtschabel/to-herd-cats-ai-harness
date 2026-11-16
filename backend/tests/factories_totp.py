"""TOTP in tests: a settable clock for codes and waiting sign-ins, and a person with
TOTP set up through the API."""

import base64
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.models_base import utcnow
from app.modules.totp import codes, timing
from tests.factories import PASSWORD
from tests.support.clock import SettableClock

TOTP = "/api/auth/me/totp"


@pytest.fixture
def totp_time(monkeypatch: pytest.MonkeyPatch, secret_key: None) -> AsyncIterator[SettableClock]:
    """The clock TOTP reads, set to now; with HERD_SECRET_KEY set."""
    clock = SettableClock(utcnow())
    monkeypatch.setattr(timing, "TOTP_CLOCK", clock)
    yield clock


@dataclass
class Enrolled:
    secret: str
    recovery_codes: list[str]
    clock: SettableClock
    used: set[int] = field(default_factory=set)

    def code(self, steps: int = 0) -> str:
        """The code `steps` steps from the clock's now."""
        step = codes.step_at(self.clock.now().timestamp()) + steps
        return codes.hotp(base64.b32decode(self.secret), step)

    def next_code(self) -> str:
        """A fresh code: moves the clock one step on first (a step is accepted once)."""
        self.clock.advance(timedelta(seconds=codes.STEP_SECONDS))
        return self.code()


async def enroll(client: AsyncClient, clock: SettableClock, password: str = PASSWORD) -> Enrolled:
    setup = await client.post(f"{TOTP}/setup", json={"password": password})
    assert setup.status_code == 200, setup.text
    enrolled = Enrolled(setup.json()["secret"], [], clock)
    confirmed = await client.post(f"{TOTP}/confirm", json={"code": enrolled.code()})
    assert confirmed.status_code == 200, confirmed.text
    enrolled.recovery_codes = confirmed.json()["recovery_codes"]
    return enrolled
