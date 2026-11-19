"""The person's own second factor (`/auth/me/totp…`) and the second step of a sign-in
(`/auth/login/second-factor`); the first step is `/auth/login` (`auth/router.py`)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.clock import Clock
from app.modules.auth.context import AuthContext
from app.modules.auth.deps import ActorDep, AuthDep, SessionDep, SettingsDep
from app.modules.auth.handover import hand_over
from app.modules.auth.me import me_out
from app.modules.auth.schemas import MeOut
from app.modules.totp.cookies import challenge_token, clear_challenge_cookie
from app.modules.totp.schemas import (
    RecoveryCodesOut,
    SecondFactorIn,
    TotpCodeIn,
    TotpSetupIn,
    TotpSetupOut,
    TotpStatusOut,
)
from app.modules.totp.service import TotpService
from app.modules.totp.sign_in import SecondStep
from app.modules.totp.timing import totp_clock

router = APIRouter(prefix="/auth", tags=["auth"])
ClockDep = Annotated[Clock, Depends(totp_clock)]


@router.get("/me/totp", response_model=TotpStatusOut)
async def my_totp(
    actor: ActorDep, session: SessionDep, settings: SettingsDep, clock: ClockDep
) -> TotpStatusOut:
    status = await TotpService(session, settings, clock).status(actor)
    return TotpStatusOut(
        enabled_at=status.enabled_at,
        recovery_codes_left=status.recovery_codes_left,
        unavailable=status.unavailable,
    )


@router.post("/me/totp/setup", response_model=TotpSetupOut)
async def set_up_totp(
    body: TotpSetupIn, actor: ActorDep, session: SessionDep, settings: SettingsDep, clock: ClockDep
) -> TotpSetupOut:
    """A new secret (the current password proves it is the person); it protects
    nothing until `/me/totp/confirm`. Shown this once."""
    setup = await TotpService(session, settings, clock).begin_setup(actor, body.password)
    return TotpSetupOut(secret=setup.secret, uri=setup.uri)


@router.post("/me/totp/confirm", response_model=RecoveryCodesOut)
async def confirm_totp(
    body: TotpCodeIn,
    actor: ActorDep,
    ctx: AuthDep,
    session: SessionDep,
    settings: SettingsDep,
    clock: ClockDep,
) -> RecoveryCodesOut:
    """The first code turns TOTP on; every other session of the person ends."""
    service = TotpService(session, settings, clock)
    fresh = await service.confirm(actor, body.code, keep_session=ctx.session_id)
    return RecoveryCodesOut(recovery_codes=fresh)


@router.post("/me/totp/disable", status_code=204)
async def disable_totp(
    body: SecondFactorIn,
    actor: ActorDep,
    session: SessionDep,
    settings: SettingsDep,
    clock: ClockDep,
) -> None:
    await TotpService(session, settings, clock).disable(actor, body.proof())


@router.post("/me/totp/recovery-codes", response_model=RecoveryCodesOut)
async def renew_recovery_codes(
    body: TotpCodeIn, actor: ActorDep, session: SessionDep, settings: SettingsDep, clock: ClockDep
) -> RecoveryCodesOut:
    """A new set in place of the old one (a current code proves the device)."""
    fresh = await TotpService(session, settings, clock).renew_recovery_codes(actor, body.code)
    return RecoveryCodesOut(recovery_codes=fresh)


@router.post("/login/second-factor", response_model=MeOut)
async def second_factor(
    body: SecondFactorIn,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    clock: ClockDep,
) -> MeOut:
    """The second step of a sign-in: the browser's waiting sign-in (cookie) and a code
    or a recovery code; the login session opens only now."""
    ip = request.client.host if request.client else None
    token = challenge_token(request, settings)
    signed_in = await SecondStep(session, settings, clock).finish(token, body.proof(), ip)
    await hand_over(session, settings, request, response, signed_in.session_token)
    clear_challenge_cookie(response, request, settings)
    return await me_out(AuthContext(user=signed_in.user), session, settings)
