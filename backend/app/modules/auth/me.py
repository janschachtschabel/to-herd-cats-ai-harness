"""`/auth/me`'s answer, the same after every way of signing in."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.auth.context import AuthContext
from app.modules.auth.schemas import MeOut, SessionLimitsOut
from app.modules.auth.service import AuthService
from app.modules.orgs.schemas import OrgOut
from app.modules.users.schemas import UserOut


async def me_out(ctx: AuthContext, session: AsyncSession, settings: Settings) -> MeOut:
    service = AuthService(session, settings)
    return MeOut(
        user=UserOut.model_validate(ctx.user),
        org=OrgOut.model_validate(await service.organization(ctx)),
        permissions=await service.permissions(ctx),
        ai_model=await service.ai_model(ctx),
        session_limits=SessionLimitsOut(
            idle_hours=settings.session_idle_hours or None, ttl_hours=settings.session_ttl_hours
        ),
    )
