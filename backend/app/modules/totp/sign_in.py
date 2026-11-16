"""The two-step sign-in of a person with TOTP (plan M9 task 16).

The first step (password, or an OIDC provider) opens no session: it leaves a
`sign_in_challenge` and gives the browser its random token in an HttpOnly cookie
(`cookies.py`). The second step names a TOTP code or a recovery code; only then is
the login session opened, and the challenge is deleted in that transaction (used
once). A challenge lasts `CHALLENGE_MINUTES`; `MAX_CHALLENGE_FAILURES` wrong codes end
it (back to the first step). Wrong codes also count per person (`factor.py`), and every
request counts per client address with the password step's limit, so the second step
is no cheaper to guess at than the first.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import RateLimited, Unauthorized
from app.core.models_base import utcnow
from app.core.ratelimit import RateLimiter, limit_key
from app.core.security import hash_token
from app.modules.auth.service import AuthService
from app.modules.auth.sign_in_log import log_sign_in
from app.modules.totp.challenges import MAX_CHALLENGE_FAILURES
from app.modules.totp.factor import Proof, SecondFactor
from app.modules.totp.models import SignInChallenge
from app.modules.totp.repository import ChallengeRepository, TotpRepository
from app.modules.totp.timing import totp_clock
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, slots=True)
class SignedIn:
    user: User
    session_token: str


class SecondStep:
    def __init__(self, session: AsyncSession, settings: Settings, clock: Clock | None = None):
        self.session = session
        self.settings = settings
        self.clock = clock or totp_clock()
        self.challenges = ChallengeRepository(session)

    async def finish(self, token: str | None, proof: Proof, ip: str | None) -> SignedIn:
        try:
            signed_in, method = await self._finish(token, proof, ip)
        except (Unauthorized, RateLimited) as refused:
            log_sign_in("second_factor", refused.code.removeprefix("auth."), client=ip)
            raise
        log_sign_in(method, "ok", client=ip, user_id=signed_in.user.id)
        return signed_in

    async def _finish(
        self, token: str | None, proof: Proof, ip: str | None
    ) -> tuple[SignedIn, str]:
        per_ip = RateLimiter(self.session, limit=self.settings.login_ip_rate_limit_per_minute)
        if await per_ip.acquire(f"login-ip:{limit_key(ip)}") is None:  # commits
            raise RateLimited(code="auth.too_many_attempts")
        token_hash = hash_token(token) if token else None
        found = await self.challenges.find(token_hash, self.clock.now()) if token_hash else None
        if found is None:
            raise Unauthorized(code="auth.second_factor_expired")
        factor = SecondFactor(
            self.session,
            found.org_id,
            failures_per_minute=self.settings.login_rate_limit_per_minute,
            clock=self.clock,
        )
        attempt = await factor.begin(found.user_id)  # commits
        challenge = await self.challenges.find(found.token_hash, self.clock.now(), lock=True)
        user = await self._user(challenge)
        totp = await TotpRepository(self.session, found.org_id).active(found.user_id)
        if challenge is None or user is None or totp is None:
            if challenge is not None and user is not None:  # TOTP was reset meanwhile
                await self.challenges.drop(challenge)
            await factor.passed(found.user_id, attempt)
            await self.session.commit()  # a dropped challenge stays dropped
            raise Unauthorized(code="auth.second_factor_expired")
        method = await factor.check(totp, proof)
        if method is None:
            await self.challenges.count_failure(challenge, MAX_CHALLENGE_FAILURES)
            await factor.failed(user.id, attempt)  # commits the failure count too
            raise Unauthorized(code="auth.second_factor_invalid")
        await factor.passed(user.id, attempt)
        await self.challenges.drop(challenge)
        session_token = await AuthService(self.session, self.settings).open_session(user, utcnow())
        return SignedIn(user, session_token), f"{challenge.method}+{method}"

    async def _user(self, challenge: SignInChallenge | None) -> User | None:
        """The challenge's person, if still active (deactivated meanwhile: no entry)."""
        if challenge is None:
            return None
        user = await UserRepository(self.session).get_current(challenge.org_id, challenge.user_id)
        if user is None or not user.is_active:
            await self.challenges.drop(challenge)
            return None
        return user
