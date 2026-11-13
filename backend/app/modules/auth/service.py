"""Login, logout and session resolution."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, actor_for, system_permissions
from app.core.config import Settings
from app.core.errors import RateLimited, Unauthorized
from app.core.models_base import utcnow
from app.core.ratelimit import RateLimiter
from app.core.security import (
    hash_token,
    new_session_token,
    verify_against_dummy,
    verify_password_async,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.models import UserSession
from app.modules.auth.repository import SessionRepository
from app.modules.orgs.models import Organization
from app.modules.orgs.repository import OrganizationRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

EXPIRED_SESSION_BATCH = 500


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.sessions = SessionRepository(session)
        self.users = UserRepository(session)
        self.orgs = OrganizationRepository(session)
        self.settings = settings

    async def login(self, email: str, password: str, ip: str | None) -> tuple[User, str]:
        """A new session for the person; the token goes into the cookie and nowhere else.

        Two limits, both checked before any password is hashed: attempts per client
        address, whatever the email (bounds the hashing one client can cause), and
        failed attempts per client address and email (guessing one account). Only
        failures count for the second, and only from that address, so nobody at
        another address can lock the person out. Without a usable account a dummy
        hash is verified, so the answer takes as long either way. Single organisation
        per installation: the person is looked up in it."""
        address = ip or "unknown"
        per_ip = RateLimiter(self.session, limit=self.settings.login_ip_rate_limit_per_minute)
        if await per_ip.acquire(f"login-ip:{address}") is None:
            raise RateLimited(code="auth.too_many_attempts")
        per_account = RateLimiter(self.session, limit=self.settings.login_rate_limit_per_minute)
        attempt = await per_account.acquire(f"login-fail:{address}:{email.lower()}")
        if attempt is None:
            raise RateLimited(code="auth.too_many_attempts")
        org = await self.orgs.get_default()
        user = await self.users.get_by_email(org.id, email) if org else None
        if user is None or not user.is_active or user.password_hash is None:
            await verify_against_dummy(password)
            raise Unauthorized(code="auth.invalid_credentials")
        if not await verify_password_async(user.password_hash, password):
            raise Unauthorized(code="auth.invalid_credentials")
        await per_account.release(attempt)  # a success is not a failed attempt
        token = new_session_token()
        now = utcnow()
        # Housekeeping without a background task: every login removes a bounded batch
        # of expired sessions, anyone's (people who never return included).
        await self.sessions.delete_expired(user.org_id, now, EXPIRED_SESSION_BATCH)
        await self.sessions.add(
            UserSession(
                org_id=user.org_id,
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=now + timedelta(hours=self.settings.session_ttl_hours),
            )
        )
        user.last_login_at = now
        return user, token

    async def logout(self, token: str) -> None:
        await self.sessions.delete_by_hash(hash_token(token))

    async def resolve(self, token: str) -> AuthContext | None:
        user_session = await self.sessions.get_active(hash_token(token), utcnow())
        if user_session is None or not user_session.user.is_active:
            return None
        return AuthContext(user=user_session.user, session_id=user_session.id)

    async def organization(self, ctx: AuthContext) -> Organization:
        return await self.orgs.get(ctx.org_id)

    async def permissions(self, ctx: AuthContext) -> list[Action]:
        """The system-wide actions the caller holds now."""
        return await system_permissions(self.session, await actor_for(self.session, ctx))
