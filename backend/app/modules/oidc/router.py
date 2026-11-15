"""OIDC routes for everyone: the providers to offer on the sign-in page, the start and
the provider's callback (browser navigations, answered with redirects to pages of the
app carrying a fixed code), and a person's own linked accounts.

The callback's query (code, state) is in no log line or trace span
(`core/telemetry.py` leaves the route out; the request log has the route template
only)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.core.errors import AppError
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.auth.cookies import cookie_name, secure_cookie, set_session_cookie
from app.modules.auth.deps import ActorDep, AuthDep, SessionDep, SettingsDep
from app.modules.oidc.flow import BINDING_COOKIE, COOKIE_PATH, FLOW_MINUTES, LOGIN_PAGE, FlowService
from app.modules.oidc.identities import IdentityService
from app.modules.oidc.metrics import count_outcome
from app.modules.oidc.protocol import ProviderFailure
from app.modules.oidc.repository import ProviderRepository
from app.modules.oidc.schemas import IdentityOut, LinkStartOut, PublicProviderOut
from app.modules.orgs.repository import OrganizationRepository

router = APIRouter(tags=["oidc"])
_FLOW = COOKIE_PATH.removeprefix("/api")


def _client(request: Request) -> str | None:
    return request.client.host if request.client else None


def _binding_cookie(request: Request, settings: SettingsDep) -> tuple[str, str]:
    """Name and path of the binding cookie: `__Host-herd_oidc` on Path=/ when secure
    (ASVS 5.0 V3.3.3, no other host can plant one), else the flow's path only."""
    name = cookie_name(request, settings, BINDING_COOKIE)
    return name, "/" if name != BINDING_COOKIE else COOKIE_PATH


def _set_binding(response: Response, request: Request, settings: SettingsDep, binding: str) -> None:
    name, path = _binding_cookie(request, settings)
    response.set_cookie(
        name,
        binding,
        max_age=FLOW_MINUTES * 60,
        httponly=True,
        secure=secure_cookie(request, settings),
        samesite="lax",
        path=path,
    )


@router.get("/auth/providers", response_model=Page[PublicProviderOut])
async def list_providers(
    params: Annotated[PageParams, Query()], session: SessionDep
) -> Page[PublicProviderOut]:
    """The enabled providers (key, name, kind) for the sign-in page; no session needed."""
    org = await OrganizationRepository(session).get_default()
    if org is None:
        return Page[PublicProviderOut](items=[])
    after = decode_id_cursor(params.cursor) if params.cursor else None
    providers = ProviderRepository(session, org.id)
    rows = await providers.page(after, params.limit + 1, enabled_only=True)
    page = id_page(rows, params.limit, lambda p: p.id)
    return Page[PublicProviderOut](
        items=[PublicProviderOut(key=p.key, name=p.name, kind=p.kind) for p in page.items],
        next_cursor=page.next_cursor,
    )


@router.get(f"{_FLOW}/{{key}}/start", status_code=302, response_class=RedirectResponse)
async def start(
    key: str, request: Request, session: SessionDep, settings: SettingsDep
) -> RedirectResponse:
    """To the provider's sign-in page, with the browser binding as a cookie; a provider
    that is unknown, off or unreachable sends the browser back to the sign-in page."""
    try:
        started = await FlowService(session, settings).start(key, _client(request))
    except (AppError, ProviderFailure) as refused:
        count_outcome(refused.code.removeprefix("oidc."))
        return RedirectResponse(f"{LOGIN_PAGE}?error={refused.code}", status_code=302)
    response = RedirectResponse(started.url, status_code=302)
    _set_binding(response, request, settings, started.binding)
    return response


@router.get(f"{_FLOW}/{{key}}/callback", status_code=302, response_class=RedirectResponse)
async def callback(
    key: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    state: Annotated[str | None, Query(max_length=512)] = None,
    code: Annotated[str | None, Query(max_length=4096)] = None,
    error: Annotated[str | None, Query(max_length=256)] = None,
) -> RedirectResponse:
    """The provider's redirect: finish the flow, then the app's start page signed in,
    or the sign-in (profile) page with `?error=` (`?link_error=`) and a fixed code."""
    binding_name, binding_path = _binding_cookie(request, settings)
    finished = await FlowService(session, settings).finish(
        key,
        _client(request),
        binding=request.cookies.get(binding_name),
        state=state,
        code=code,
        error=error,
    )
    response = RedirectResponse(finished.location, status_code=302)
    response.delete_cookie(
        binding_name,
        path=binding_path,
        secure=secure_cookie(request, settings),
        httponly=True,
        samesite="lax",
    )
    if finished.session_token is not None:
        set_session_cookie(response, request, settings, finished.session_token)
    return response


@router.post("/auth/me/identities/{key}/link", response_model=LinkStartOut)
async def link(
    key: str,
    request: Request,
    response: Response,
    ctx: AuthDep,
    session: SessionDep,
    settings: SettingsDep,
) -> LinkStartOut:
    """Start linking the caller's account at the provider (from the profile): the
    browser goes to the returned address; the binding cookie comes with this answer."""
    service = FlowService(session, settings)
    started = await service.start(key, _client(request), link_session=ctx)
    _set_binding(response, request, settings, started.binding)
    return LinkStartOut(url=started.url)


@router.get("/auth/me/identities", response_model=Page[IdentityOut])
async def my_identities(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[IdentityOut]:
    page = await IdentityService(session).list(actor, actor.principal.id, params)
    return Page[IdentityOut](
        items=[IdentityOut.of(i, p) for i, p in page.items], next_cursor=page.next_cursor
    )


@router.delete("/auth/me/identities/{identity_id}", status_code=204)
async def unlink_mine(identity_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await IdentityService(session).unlink(actor, actor.principal.id, identity_id)
