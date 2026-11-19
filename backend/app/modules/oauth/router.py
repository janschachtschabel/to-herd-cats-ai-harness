"""OAuth routes: the organisation's OAuth clients (`ai.manage`; anyone else: 404
`ai.not_found`) and the callbacks the authorization server sends the browser back to:
each app's own, and the shared one of earlier releases for flows started with it
(`callbacks.py`, J13).

A callback needs no session to answer: without one, or with a state that is not the
caller's, it sends the browser to the result page of the app's purpose with
`status=invalid` (`/calendar/accounts` for a calendar app, else `/ai/oauth/done`). Its query
(code, state, iss) is in no log line or trace span (`core/telemetry.py` leaves the
routes out); the result page's address carries a fixed status only."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.core.pagination import Page, PageParams
from app.modules.auth.cookies import session_token
from app.modules.auth.deps import ActorDep, SessionDep, SettingsDep
from app.modules.auth.service import AuthService
from app.modules.oauth.callbacks import CALLBACK_PATH, LEGACY_CALLBACK_PATH, callback_url
from app.modules.oauth.clients import ClientService
from app.modules.oauth.flow import FlowService, Response
from app.modules.oauth.models import OAuthClient
from app.modules.oauth.schemas import (
    ClientCreate,
    ClientOut,
    ClientUpdate,
    DiscoverIn,
    DiscoveryOut,
)

clients = APIRouter(prefix="/ai/oauth-clients", tags=["oauth"])
callback = APIRouter(tags=["oauth"])


def _out(client: OAuthClient) -> ClientOut:
    return ClientOut.of(client, callback_url(client.id))


@clients.get("", response_model=Page[ClientOut])
async def list_clients(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[ClientOut]:
    page = await ClientService(session).list(actor, params)
    return Page[ClientOut](items=[_out(c) for c in page.items], next_cursor=page.next_cursor)


@clients.post("", response_model=ClientOut, status_code=201)
async def create_client(body: ClientCreate, actor: ActorDep, session: SessionDep) -> ClientOut:
    return _out(await ClientService(session).create(actor, body))


@clients.post("/discover", response_model=DiscoveryOut)
async def discover_client(body: DiscoverIn, actor: ActorDep, session: SessionDep) -> DiscoveryOut:
    """Find an MCP server's authorization server (RFC 9728, RFC 8414): a proposal for
    a client; nothing is stored, every request goes through the egress guard."""
    found = await ClientService(session).discover(actor, body.url)
    return DiscoveryOut.model_validate(found, from_attributes=True)


@clients.get("/{client_id}", response_model=ClientOut)
async def get_client(client_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> ClientOut:
    return _out(await ClientService(session).get(actor, client_id))


@clients.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: uuid.UUID, body: ClientUpdate, actor: ActorDep, session: SessionDep
) -> ClientOut:
    return _out(await ClientService(session).update(actor, client_id, body))


@clients.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> None:
    await ClientService(session).delete(actor, client_id, version)


State = Annotated[str | None, Query(max_length=512)]
Code = Annotated[str | None, Query(max_length=4096)]
Error = Annotated[str | None, Query(max_length=256)]
Iss = Annotated[str | None, Query(max_length=500)]


async def _finish(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    response: Response,
    via: uuid.UUID | None,
) -> RedirectResponse:
    token = session_token(request, settings)
    auth = await AuthService(session, settings).resolve(token) if token else None
    finished = await FlowService(session).finish(auth, response, via)
    return RedirectResponse(finished.location(), status_code=303)


@callback.get(CALLBACK_PATH.removeprefix("/api"), status_code=303, response_class=RedirectResponse)
async def oauth_callback(
    client_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    state: State = None,
    code: Code = None,
    error: Error = None,
    iss: Iss = None,
) -> RedirectResponse:
    """An app's authorization server's redirect: finish the flow started with this
    callback, then send the browser to its purpose's result page (`?status=...`)."""
    return await _finish(request, session, settings, Response(state, code, error, iss), client_id)


@callback.get(
    LEGACY_CALLBACK_PATH.removeprefix("/api"),
    status_code=303,
    response_class=RedirectResponse,
)
async def oauth_legacy_callback(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    state: State = None,
    code: Code = None,
    error: Error = None,
    iss: Iss = None,
) -> RedirectResponse:
    """The shared callback of earlier releases: only for flows started with it."""
    return await _finish(request, session, settings, Response(state, code, error, iss), None)
