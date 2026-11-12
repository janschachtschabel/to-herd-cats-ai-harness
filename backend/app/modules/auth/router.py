from fastapi import APIRouter, Request, Response

from app.modules.auth.context import AuthContext
from app.modules.auth.deps import AuthDep, SessionDep, SettingsDep
from app.modules.auth.schemas import LoginRequest, MeOut
from app.modules.auth.service import AuthService
from app.modules.orgs.schemas import OrgOut
from app.modules.users.schemas import UserOut

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
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
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


async def _me(ctx: AuthContext, session: SessionDep, settings: SettingsDep) -> MeOut:
    service = AuthService(session, settings)
    return MeOut(
        user=UserOut.model_validate(ctx.user),
        org=OrgOut.model_validate(await service.organization(ctx)),
        permissions=await service.permissions(ctx),
    )
