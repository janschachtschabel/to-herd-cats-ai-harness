"""Login, logout and session resolution."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, actor_for, system_permissions
from app.core.config import Settings
from app.core.errors import RateLimited, Unauthorized
from app.core.failure_limit import FailureLimiter
from app.core.models_base import utcnow
from app.core.ratelimit import RateLimiter, limit_key
from app.core.retention import upkeep_after
from app.core.security import (
    hash_token,
    new_session_token,
    password_work,
    verify_against_dummy,
    verify_password_async,
)
from app.modules.ai.effective import effective_assignment
from app.modules.auth.context import AuthContext
from app.modules.auth.models import UserSession
from app.modules.auth.repository import SessionRepository
from app.modules.orgs.models import Organization
from app.modules.orgs.repository import OrganizationRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

EXPIRED_SESSION_BATCH = 500
# Ended sessions (logout, expiry) are kept this long, so live editing can still save
# the last edits of a person whose session ended mid-session (review M2 R2).
ENDED_SESSION_KEEP = upkeep_after("user_session")


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.sessions = SessionRepository(session)
        self.users = UserRepository(session)
        self.orgs = OrganizationRepository(session)
        self.settings = settings

    async def login(self, email: str, password: str, ip: str | None) -> tuple[User, str]:
        async with password_work():  # refused at once, before any query, when full
            return await self._login(email, password, ip)

    async def _login(self, email: str, password: str, ip: str | None) -> tuple[User, str]:
        """A new session for the person; the token goes into the cookie and nowhere else.

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
        # Read again: the person may have been deactivated or got a new password
        # while the password was being checked.
        await self.session.refresh(user)
        if not user.is_active or user.password_hash != checked:
            await self.session.commit()
            raise Unauthorized(code="auth.invalid_credentials")
        return user, await self.open_session(user, utcnow())

    async def open_session(self, user: User, now: datetime) -> str:
        """A new login session for an active person whose sign-in was checked (password
        or OIDC); the token goes into the cookie and nowhere else."""
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
            )
        )
        user.last_login_at = now
        return token

    async def logout(self, token: str) -> None:
        await self.sessions.end_by_hash(hash_token(token), utcnow())

    async def resolve(self, token: str) -> AuthContext | None:
        user_session = await self.sessions.get_active(hash_token(token), utcnow())
        if user_session is None or not user_session.user.is_active:
            return None
        return AuthContext(user=user_session.user, session_id=user_session.id)

    async def resolve_session(self, session_id: uuid.UUID) -> AuthContext | None:
        """The caller of a login session known by its id (live editing checks again
        whether the session of an open connection still holds)."""
        user_session = await self.sessions.get_active_by_id(session_id, utcnow())
        if user_session is None or not user_session.user.is_active:
            return None
        return AuthContext(user=user_session.user, session_id=user_session.id)

    async def resolve_ended_session(self, session_id: uuid.UUID) -> AuthContext | None:
        """The caller of a login session that ended by logout or expiry, while the
        person is still active (deactivation and an administrator's or a password
        change's sign-out delete the session instead)."""
        user_session = await self.sessions.get_by_id(session_id)
        if user_session is None or user_session.expires_at > utcnow():
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
