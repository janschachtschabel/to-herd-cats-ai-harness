"""A step that needs the second factor of a person who has one (plan M9 task 16):
creating an access token, personal or an external agent's (ASVS 5.0 V6.3.4: a token
is a way in and must not be easier to get than a sign-in). People without TOTP, and
agents, pass without a code.

Commits the attempt's count (`factor.py`): call it after the reads that decide the
request and before anything is written."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.config import get_settings
from app.core.errors import Forbidden, ValidationFailed
from app.core.principal import PrincipalType
from app.modules.totp.factor import Proof, SecondFactor
from app.modules.totp.repository import TotpRepository


async def require_second_factor(session: AsyncSession, actor: Actor, code: str | None) -> None:
    """403 `auth.second_factor_required` without a code, 422 `auth.second_factor_invalid`
    for a wrong or used one, 429 once the person's failures are used up."""
    if actor.principal.type != PrincipalType.USER:
        return
    totp = await TotpRepository(session, actor.org_id).active(actor.principal.id)
    if totp is None:
        return
    if code is None:
        raise Forbidden(code="auth.second_factor_required")
    limit = get_settings().login_rate_limit_per_minute
    factor = SecondFactor(session, actor.org_id, failures_per_minute=limit)
    if await factor.verify(totp, Proof(code=code)) is None:
        raise ValidationFailed(code="auth.second_factor_invalid")
