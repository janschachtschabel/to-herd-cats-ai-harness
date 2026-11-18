"""Signing in again before a sensitive change (ASVS 5.0 V7.5.1, J9): linking a new
account at a provider (a new way into the account) needs the person's password, or a
sign-in through a provider that opened this very session at most `WINDOW` ago (people
without a password). Wrong passwords count like those of a password change (same key,
same limit)."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Forbidden, RateLimited, ValidationFailed
from app.core.ratelimit import RateLimiter
from app.core.security import verify_password_async
from app.modules.auth.context import AuthContext
from app.modules.auth.repository import SessionRepository
from app.modules.auth.timing import session_clock

WINDOW = timedelta(minutes=10)


async def require_recent_sign_in(
    session: AsyncSession, settings: Settings, ctx: AuthContext, password: str | None
) -> None:
    """Passes, or raises 403 `auth.reauth_required` (neither a password nor a fresh
    sign-in), 422 `auth.wrong_password`, 429 `auth.too_many_attempts`."""
    if password:
        await _check_password(session, settings, ctx, password)
        return
    since = session_clock().now() - WINDOW
    current = await SessionRepository(session).get_by_id(ctx.session_id) if ctx.session_id else None
    if current is None or current.reauth_at is None or current.reauth_at < since:
        raise Forbidden(code="auth.reauth_required")


async def _check_password(
    session: AsyncSession, settings: Settings, ctx: AuthContext, password: str
) -> None:
    limiter = RateLimiter(session, limit=settings.login_rate_limit_per_minute)
    attempt = await limiter.acquire(f"password-fail:{ctx.user.id}")  # commits
    if attempt is None:
        raise RateLimited(code="auth.too_many_attempts")
    checked = ctx.user.password_hash
    if checked is None or not await verify_password_async(checked, password):
        raise ValidationFailed(code="auth.wrong_password")
    await limiter.release(attempt)
