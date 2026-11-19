"""Checking a person's second factor: a TOTP code or a recovery code.

Failed checks count per person (`second-factor-fail:<id>`, `FailureLimiter`, the
login limit per minute, `HERD_LOGIN_RATE_LIMIT_PER_MINUTE`), whatever asks: the second
step of a sign-in, turning TOTP off, a new set of recovery codes, a new access token.
They also count on the TOTP row for a lasting lock (review M9b F9): LOCK_AFTER wrong
codes within LOCK_WINDOW lock the second factor for LOCK_FOR (429
`auth.second_factor_locked`, a correct code included), audited as `user.totp_locked`
(system) and told to the person in her activity (`totp_locked`); a correct code starts
the count again. Times come from the TOTP clock.
A correct code passes once: its time step must be newer than the last one accepted
(`TotpRepository.use_step`), a recovery code is deleted as it is accepted. Neither the
secret nor a code is ever logged or audited.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.clock import Clock
from app.core.errors import RateLimited
from app.core.failure_limit import FailureLimiter
from app.modules.audit.recorder import record_system
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.notification_repository import NotificationRepository
from app.modules.totp import codes, recovery
from app.modules.totp.lock_repository import TotpLockRepository
from app.modules.totp.models import UserTotp
from app.modules.totp.repository import TotpRepository
from app.modules.totp.timing import totp_clock

LOCK_AFTER = 10
LOCK_WINDOW = timedelta(hours=24)
LOCK_FOR = timedelta(hours=1)


class Method(StrEnum):
    TOTP = "totp"
    RECOVERY_CODE = "recovery_code"


@dataclass(frozen=True, slots=True)
class Proof:
    """What the person typed: exactly one of the two (the schemas see to it)."""

    code: str | None = None
    recovery_code: str | None = None


class SecondFactor:
    def __init__(
        self,
        session: AsyncSession,
        org_id: uuid.UUID,
        *,
        failures_per_minute: int,
        clock: Clock | None = None,
    ) -> None:
        self.session = session
        self.org_id = org_id
        self.totps = TotpRepository(session, org_id)
        self.locks = TotpLockRepository(session, org_id)
        self.failures_per_minute = failures_per_minute
        self.clock = clock or totp_clock()

    def limiter(self, user_id: uuid.UUID) -> FailureLimiter:
        return FailureLimiter(
            self.session, f"second-factor-fail:{user_id}", limit=self.failures_per_minute
        )

    async def begin(self, user_id: uuid.UUID) -> uuid.UUID:
        """A place among the person's attempts (429 when the failures are used up, or
        while the second factor is locked). Commits: call it before taking any lock."""
        until = await self.locks.locked_until(user_id)
        if until is not None and until > self.clock.now():
            await self.session.commit()
            raise RateLimited(code="auth.second_factor_locked")
        attempt = await self.limiter(user_id).begin()
        if attempt is None:
            raise RateLimited(code="auth.too_many_attempts")
        return attempt

    async def check(self, totp: UserTotp, proof: Proof) -> Method | None:
        """Whether `proof` holds for this TOTP, using up the step or the code if so;
        part of the caller's transaction, never commits."""
        if proof.code is not None:
            try:
                secret = secrets.resolve(totp.secret_ref).get_secret_value()
            except secrets.SecretUnavailable:
                return None  # no key (or another key): only a recovery code helps
            step = codes.matching_step(secret, proof.code, self.clock.now().timestamp())
            if step is not None and await self.totps.use_step(totp.id, step):
                return Method.TOTP
            return None
        if proof.recovery_code is not None:
            used = await self.totps.use_recovery_code(
                totp.user_id, recovery.digest(proof.recovery_code)
            )
            return Method.RECOVERY_CODE if used else None
        return None

    async def passed(self, user_id: uuid.UUID, attempt: uuid.UUID) -> None:
        await self.limiter(user_id).end(attempt)
        await self.locks.reset(user_id)

    async def failed(self, user_id: uuid.UUID, attempt: uuid.UUID) -> None:
        """Counts the failure (locks at LOCK_AFTER); commits (with whatever the caller
        wrote before)."""
        now = self.clock.now()
        if await self.locks.count_failure(user_id, now, now - LOCK_WINDOW) >= LOCK_AFTER:
            await self._lock(user_id, now + LOCK_FOR)
        await self.limiter(user_id).fail(attempt)

    async def _lock(self, user_id: uuid.UUID, until: datetime) -> None:
        await self.locks.lock(user_id, until)
        details = {"until": until.isoformat()}
        await record_system(self.session, self.org_id, "user.totp_locked", "user", user_id, details)
        await NotificationRepository(self.session, self.org_id).renew_about_account(
            user_id, user_id, NotificationReason.TOTP_LOCKED
        )

    async def verify(self, totp: UserTotp, proof: Proof) -> Method | None:
        """`begin`, `check`, then `passed` or `failed`: for a signed-in person."""
        attempt = await self.begin(totp.user_id)
        method = await self.check(totp, proof)
        if method is None:
            await self.failed(totp.user_id, attempt)
        else:
            await self.passed(totp.user_id, attempt)
        return method
