from fastapi import APIRouter, Request, Response

from app.modules.auth.context import AuthContext
from app.modules.auth.cookies import set_session_cookie
from app.modules.auth.deps import ActorDep, AuthDep, SessionDep, SettingsDep
from app.modules.auth.schemas import LoginRequest, MeOut
from app.modules.auth.service import AuthService
from app.modules.orgs.schemas import OrgOut
from app.modules.users.profile import ProfileService
from app.modules.users.schemas import PasswordChangeIn, ProfileUpdateIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=MeOut)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> MeOut:
    ip = request.client.host if request.client else None
    user, token = await AuthService(session, settings).login(body.email, body.password, ip)
    set_session_cookie(response, request, settings, token)
    return await _me(AuthContext(user=user), session, settings)


@router.post("/logout", status_code=204)
async def logout(
    request: Request, response: Response, session: SessionDep, settings: SettingsDep
) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await AuthService(session, settings).logout(token)
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=MeOut)
async def me(ctx: AuthDep, session: SessionDep, settings: SettingsDep) -> MeOut:
    return await _me(ctx, session, settings)


@router.patch("/me", response_model=MeOut)
async def update_me(
    body: ProfileUpdateIn,
    actor: ActorDep,
    ctx: AuthDep,
    session: SessionDep,
    settings: SettingsDep,
) -> MeOut:
    """The caller's own settings (the language)."""
    user = await ProfileService(session).update(actor, body, body.version)
    return await _me(AuthContext(user=user, session_id=ctx.session_id), session, settings)


@router.post("/me/password", status_code=204)
async def change_my_password(
    body: PasswordChangeIn,
    actor: ActorDep,
    ctx: AuthDep,
    session: SessionDep,
    settings: SettingsDep,
) -> None:
    """The caller's own password; this session stays, every other one ends."""
    await ProfileService(session).change_password(
        actor,
        body.current_password,
        body.new_password,
        keep_session=ctx.session_id,
        failures_per_minute=settings.login_rate_limit_per_minute,
    )


async def _me(ctx: AuthContext, session: SessionDep, settings: SettingsDep) -> MeOut:
    service = AuthService(session, settings)
    return MeOut(
        user=UserOut.model_validate(ctx.user),
        org=OrgOut.model_validate(await service.organization(ctx)),
        permissions=await service.permissions(ctx),
        ai_model=await service.ai_model(ctx),
    )
