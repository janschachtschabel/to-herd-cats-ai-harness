from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.modules.auth.context import AuthContext
from app.modules.auth.cookies import clear_session_cookie, session_token, set_session_cookie
from app.modules.auth.deps import ActorDep, AuthDep, SessionDep, SettingsDep
from app.modules.auth.me import me_out
from app.modules.auth.schemas import LoginRequest, MeOut
from app.modules.auth.service import AuthService, SecondFactorNeeded
from app.modules.totp.cookies import set_challenge_cookie
from app.modules.totp.schemas import SecondFactorNeededOut
from app.modules.users.profile import ProfileService
from app.modules.users.schemas import PasswordChangeIn, ProfileUpdateIn

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=MeOut,
    responses={202: {"model": SecondFactorNeededOut, "description": "Second factor needed"}},
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> MeOut | JSONResponse:
    """Signed in (200, the session cookie), or, for a person with TOTP, 202: the
    password was right and the sign-in waits for the second factor
    (`/auth/login/second-factor`, with the cookie set here); no session yet."""
    ip = request.client.host if request.client else None
    service = AuthService(session, settings)
    result = await service.login(body.email, body.password, ip)
    if isinstance(result, SecondFactorNeeded):
        waiting = SecondFactorNeededOut(expires_at=result.expires_at)
        answer = JSONResponse(waiting.model_dump(mode="json"), status_code=202)
        set_challenge_cookie(answer, request, settings, result.challenge_token)
        return answer
    await service.end_replaced(session_token(request, settings))
    set_session_cookie(response, request, settings, result.token)
    return await _me(AuthContext(user=result.user), session, settings)


@router.post("/logout", status_code=204)
async def logout(
    request: Request, response: Response, session: SessionDep, settings: SettingsDep
) -> None:
    token = session_token(request, settings)
    if token:
        await AuthService(session, settings).logout(token)
    clear_session_cookie(response, request, settings)


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
    return await me_out(ctx, session, settings)
