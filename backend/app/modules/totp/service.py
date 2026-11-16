"""A person's own second factor (plan M9 task 16; Jan's answer J3: optional for
everyone, owners and admins included).

- Only for a password account, and only with `HERD_SECRET_KEY` set (the secret is
  stored `enc:`): otherwise `status` says why not and setting up answers 409.
- Setting up needs the current password (ASVS 5.0 V7.5.1; wrong ones count like a
  password change's) and gives the secret once, as base32 and as an `otpauth://` URI;
  nothing protects the account until the first code confirms it. Confirming returns
  ten recovery codes, once, and ends the person's other sessions and waiting sign-ins
  (they were opened without the second factor).
- Turning it off needs a current code or a recovery code; so does a new set of
  recovery codes (a code only: they replace what a lost device leaves).
- Every change is audited without a secret or a code: `user.totp_enabled`,
  `user.totp_disabled`, `user.totp_recovery_codes_renewed`.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.access import Actor
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, NotFound, RateLimited, ValidationFailed
from app.core.ratelimit import RateLimiter
from app.core.security import verify_password_async
from app.modules.audit.recorder import record
from app.modules.auth.repository import SessionRepository
from app.modules.orgs.repository import OrganizationRepository
from app.modules.totp import codes, recovery
from app.modules.totp.factor import Proof, SecondFactor
from app.modules.totp.models import UserTotp
from app.modules.totp.repository import TotpRepository
from app.modules.totp.timing import totp_clock
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

Unavailable = Literal["no_password", "no_secret_key"]


@dataclass(frozen=True, slots=True)
class TotpStatus:
    enabled_at: datetime | None
    recovery_codes_left: int
    unavailable: Unavailable | None


@dataclass(frozen=True, slots=True)
class Setup:
    secret: str
    uri: str


class TotpService:
    def __init__(self, session: AsyncSession, settings: Settings, clock: Clock | None = None):
        self.session = session
        self.settings = settings
        self.clock = clock or totp_clock()
        self.users = UserRepository(session)

    async def status(self, actor: Actor) -> TotpStatus:
        user = await self._me(actor, lock=False)
        totps = TotpRepository(self.session, actor.org_id)
        totp = await totps.active(user.id)
        if totp is None:
            return TotpStatus(None, 0, self._unavailable(user))
        return TotpStatus(totp.confirmed_at, await totps.recovery_codes_left(user.id), None)

    async def begin_setup(self, actor: Actor, password: str) -> Setup:
        user = await self._me(actor, lock=False)
        if (reason := self._unavailable(user)) is not None:
            raise Conflict(code=f"totp.{reason}")
        await self._check_password(user, password)  # commits
        user = await self._me(actor)
        totps = TotpRepository(self.session, actor.org_id)
        if await totps.active(user.id) is not None:
            raise Conflict(code="totp.already_enabled")
        secret = codes.new_secret()
        await totps.start(user.id, secrets.encrypt(secret))
        org = await OrganizationRepository(self.session).get(actor.org_id)
        return Setup(secret, codes.otpauth_uri(secret, account=user.email, issuer=org.name))

    async def confirm(
        self, actor: Actor, code: str, *, keep_session: uuid.UUID | None
    ) -> list[str]:
        """The first code turns TOTP on; the recovery codes, shown this once."""
        factor = self._factor(actor)
        attempt = await factor.begin(actor.principal.id)  # commits
        user = await self._me(actor)
        totps = TotpRepository(self.session, actor.org_id)
        totp = await totps.get(user.id, lock=True)
        if totp is None:
            await factor.passed(user.id, attempt)
            raise Conflict(code="totp.no_setup")
        if totp.confirmed_at is not None:
            await factor.passed(user.id, attempt)
            raise Conflict(code="totp.already_enabled")
        if await factor.check(totp, Proof(code=code)) is None:
            await factor.failed(user.id, attempt)
            raise ValidationFailed(code="auth.second_factor_invalid")
        await factor.passed(user.id, attempt)
        totp.confirmed_at = self.clock.now()
        fresh = await self._new_recovery_codes(totps, user.id)
        await SessionRepository(self.session).delete_for_user(
            actor.org_id, user.id, keep=keep_session
        )
        await record(self.session, actor, "user.totp_enabled", "user", user.id)
        return fresh

    async def disable(self, actor: Actor, proof: Proof) -> None:
        totp = await self._verified(actor, proof)
        await TotpRepository(self.session, actor.org_id).remove(totp.user_id)
        await record(self.session, actor, "user.totp_disabled", "user", totp.user_id)

    async def renew_recovery_codes(self, actor: Actor, code: str) -> list[str]:
        totp = await self._verified(actor, Proof(code=code))
        totps = TotpRepository(self.session, actor.org_id)
        fresh = await self._new_recovery_codes(totps, totp.user_id)
        await record(self.session, actor, "user.totp_recovery_codes_renewed", "user", totp.user_id)
        return fresh

    async def _verified(self, actor: Actor, proof: Proof) -> UserTotp:
        user = await self._me(actor, lock=False)
        totp = await TotpRepository(self.session, actor.org_id).active(user.id)
        if totp is None:
            raise Conflict(code="totp.not_enabled")
        if await self._factor(actor).verify(totp, proof) is None:
            raise ValidationFailed(code="auth.second_factor_invalid")
        return totp

    async def _new_recovery_codes(self, totps: TotpRepository, user_id: uuid.UUID) -> list[str]:
        fresh = recovery.new_codes()
        await totps.replace_recovery_codes(user_id, [recovery.digest(c) for c in fresh])
        return fresh

    async def _check_password(self, user: User, password: str) -> None:
        """Wrong passwords count like those of a password change (same key)."""
        limiter = RateLimiter(self.session, limit=self.settings.login_rate_limit_per_minute)
        attempt = await limiter.acquire(f"password-fail:{user.id}")  # commits
        if attempt is None:
            raise RateLimited(code="auth.too_many_attempts")
        checked = user.password_hash
        if checked is None or not await verify_password_async(checked, password):
            raise ValidationFailed(code="auth.wrong_password")
        await limiter.release(attempt)

    def _factor(self, actor: Actor) -> SecondFactor:
        return SecondFactor(
            self.session,
            actor.org_id,
            failures_per_minute=self.settings.login_rate_limit_per_minute,
            clock=self.clock,
        )

    def _unavailable(self, user: User) -> Unavailable | None:
        if user.password_hash is None:
            return "no_password"
        if self.settings.secret_key is None:
            return "no_secret_key"
        return None

    async def _me(self, actor: Actor, *, lock: bool = True) -> User:
        if lock:
            await self.users.lock_admin_writes(actor.org_id)
        user = await self.users.get_current(actor.org_id, actor.principal.id)
        if user is None:  # an agent, or a person deleted meanwhile
            raise NotFound(code="users.not_found")
        return user
