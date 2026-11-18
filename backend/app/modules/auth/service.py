"""Login, logout and session resolution."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, actor_for, system_permissions
from app.core.config import Settings
from app.core.errors import RateLimited, Unauthorized
from app.core.failure_limit import FailureLimiter
from app.core.ratelimit import RateLimiter, limit_key
from app.core.retention import upkeep_after
from app.core.security import (
    hash_password_async,
    hash_token,
    needs_rehash,
    new_session_token,
    password_work,
    verify_against_dummy,
    verify_password_async,
)
from app.modules.ai.effective import effective_assignment
from app.modules.auth.context import AuthContext
from app.modules.auth.models import UserSession
from app.modules.auth.repository import SessionRepository
from app.modules.auth.sign_in_log import log_sign_in, log_sign_out
from app.modules.auth.timing import session_clock
from app.modules.orgs.models import Organization
from app.modules.orgs.repository import OrganizationRepository
from app.modules.totp.challenges import open_challenge
from app.modules.totp.repository import TotpRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

EXPIRED_SESSION_BATCH = 500
# Ended sessions (logout, expiry) are kept this long, so live editing can still save
# the last edits of a person whose session ended mid-session (review M2 R2).
ENDED_SESSION_KEEP = upkeep_after("user_session")


@dataclass(frozen=True, slots=True)
class SessionOpened:
    user: User
    token: str  # for the session cookie, nowhere else


@dataclass(frozen=True, slots=True)
class SecondFactorNeeded:
    challenge_token: str  # for the waiting sign-in's cookie, nowhere else
    expires_at: datetime


type Login = SessionOpened | SecondFactorNeeded


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        idle = settings.session_idle_hours
        self.sessions = SessionRepository(session, timedelta(hours=idle) if idle else None)
        self.users = UserRepository(session)
        self.orgs = OrganizationRepository(session)
        self.settings = settings

    async def login(self, email: str, password: str, ip: str | None) -> Login:
        """A new session, or, for a person with TOTP, a sign-in waiting for the second
        factor (`totp/sign_in.py`): the password alone opens no session then."""
        try:
            async with password_work():  # refused at once, before any query, when full
                user = await self._login(email, password, ip)
        except (Unauthorized, RateLimited) as refused:
            log_sign_in("password", refused.code.removeprefix("auth."), client=ip)
            raise
        if await TotpRepository(self.session, user.org_id).active(user.id) is not None:
            challenge = await open_challenge(self.session, user, "password")
            log_sign_in("password", "second_factor", client=ip, user_id=user.id)
            return SecondFactorNeeded(challenge.token, challenge.expires_at)
        token = await self.open_session(user)
        log_sign_in("password", "ok", client=ip, user_id=user.id)
        return SessionOpened(user, token)

    async def _login(self, email: str, password: str, ip: str | None) -> User:
        """The person whose password this is; the caller opens the session.

        Two limits, both checked before any password is hashed: attempts per client
        address, whatever the email (bounds the hashing one client can cause), and
        failed attempts per client address and email (guessing one account). Only
        completed failures count for the second (`FailureLimiter`: correct logins in
        flight never use it up), and only from that address, so nobody at another
        address can lock the person out. An IPv6 address counts by its /64. Without a
        usable account a dummy hash is verified, so the answer takes as long either
        way. Single organisation per installation: the person is looked up in it."""
        address = limit_key(ip)
        per_ip = RateLimiter(self.session, limit=self.settings.login_ip_rate_limit_per_minute)
        if await per_ip.acquire(f"login-ip:{address}") is None:
            raise RateLimited(code="auth.too_many_attempts")
        per_account = FailureLimiter(
            self.session,
            f"login-fail:{address}:{email.lower()}",
            limit=self.settings.login_rate_limit_per_minute,
        )
        attempt = await per_account.begin()
        if attempt is None:
            raise RateLimited(code="auth.too_many_attempts")
        org = await self.orgs.get_default()
        user = await self.users.get_by_email(org.id, email) if org else None
        checked = user.password_hash if user is not None and user.is_active else None
        await self.session.commit()  # no connection is held while hashing
        valid = await _verify(checked, password)  # admitted already: never refused
        if user is None or not valid:
            await per_account.fail(attempt)
            raise Unauthorized(code="auth.invalid_credentials")
        await per_account.end(attempt)  # a success is not a failed attempt
        # Today's hashing parameters, computed before the person's row is read again
        # (no connection held while hashing).
        rehashed = await hash_password_async(password) if needs_rehash(checked or "") else None
        # Read again: the person may have been deactivated or got a new password
        # while the password was being checked.
        await self.session.refresh(user)
        if not user.is_active or user.password_hash != checked:
            await self.session.commit()
            raise Unauthorized(code="auth.invalid_credentials")
        if rehashed is not None:
            user.password_hash = rehashed
        return user

    async def open_session(self, user: User) -> str:
        """A new login session for an active person whose sign-in was checked (password
        or OIDC); the token goes into the cookie and nowhere else (`handover.py`)."""
        now = session_clock().now()
        token = new_session_token()
        # Housekeeping without a background task: every login removes a bounded batch
        # of expired sessions, anyone's (people who never return included).
        await self.sessions.delete_expired(
            user.org_id, now - ENDED_SESSION_KEEP, EXPIRED_SESSION_BATCH
        )
        await self.sessions.add(
            UserSession(
                org_id=user.org_id,
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=now + timedelta(hours=self.settings.session_ttl_hours),
                last_used_at=now,
                signed_in_at=now,
            )
        )
        user.last_login_at = now
        return token

    async def end_replaced(self, token: str | None) -> None:
        """A sign-in replaces the browser's session: the token it had ends (ASVS 5.0
        V7.2.4), whoever it belonged to."""
        if token:
            await self.sessions.end_by_hash(hash_token(token), session_clock().now())

    async def logout(self, token: str) -> None:
        ended = await self.sessions.end_by_hash(hash_token(token), session_clock().now())
        if ended is not None:
            log_sign_out(ended)

    async def resolve(self, token: str, *, use: bool = False) -> AuthContext | None:
        """The caller of a running session. `use`: the request counts as the session's
        use (J7): its last use is noted, at most once a minute, and committed at once,
        so no row lock is held for the rest of the request."""
        now = session_clock().now()
        user_session = await self.sessions.get_active(hash_token(token), now)
        if user_session is None or not user_session.user.is_active:
            return None
        if use and await self.sessions.touch(user_session.id, now):
            await self.session.commit()
        return AuthContext(user=user_session.user, session_id=user_session.id)

    async def resolve_session(self, session_id: uuid.UUID) -> AuthContext | None:
        """The caller of a login session known by its id (live editing checks again
        whether the session of an open connection still holds)."""
        user_session = await self.sessions.get_active_by_id(session_id, session_clock().now())
        if user_session is None or not user_session.user.is_active:
            return None
        return AuthContext(user=user_session.user, session_id=user_session.id)

    async def resolve_ended_session(self, session_id: uuid.UUID) -> AuthContext | None:
        """The caller of a login session that ended by logout, expiry or idleness, while
        the person is still active (deactivation and an administrator's or a password
        change's sign-out delete the session instead)."""
        user_session = await self.sessions.get_by_id(session_id)
        if user_session is None or not self.sessions.ended(user_session, session_clock().now()):
            return None
        if not user_session.user.is_active:
            return None
        return AuthContext(user=user_session.user, session_id=user_session.id)

    async def organization(self, ctx: AuthContext) -> Organization:
        return await self.orgs.get(ctx.org_id)

    async def permissions(self, ctx: AuthContext) -> list[Action]:
        """The system-wide actions the caller holds now."""
        return await system_permissions(self.session, await actor_for(self.session, ctx))

    async def ai_model(self, ctx: AuthContext) -> str | None:
        """The model of the caller's effective AI assignment, if they have `ai.use`."""
        effective = await effective_assignment(self.session, ctx.org_id, ctx.user.id)
        return effective.model if effective else None


async def _verify(password_hash: str | None, password: str) -> bool:
    """Without a usable account the dummy hash is verified: the answer takes as long."""
    if password_hash is None:
        await verify_against_dummy(password)
        return False
    return await verify_password_async(password_hash, password)
