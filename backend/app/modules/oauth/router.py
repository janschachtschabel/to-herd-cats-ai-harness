"""OAuth routes: the organisation's OAuth clients (`ai.manage`; anyone else: 404
`ai.not_found`) and the callback the authorization server sends the browser back to.

The callback needs no session to answer: without one, or with a state that is not
the caller's, it sends the browser to the result page with `status=invalid`. Its
query (code, state) is in no log line or trace span (`core/telemetry.py` leaves the
route out); the result page's address carries a fixed status only."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep, SettingsDep
from app.modules.auth.service import AuthService
from app.modules.oauth.clients import ClientService
from app.modules.oauth.flow import CALLBACK_PATH, FlowService
from app.modules.oauth.schemas import (
    ClientCreate,
    ClientOut,
    ClientUpdate,
    DiscoverIn,
    DiscoveryOut,
)

clients = APIRouter(prefix="/ai/oauth-clients", tags=["oauth"])
callback = APIRouter(tags=["oauth"])


@clients.get("", response_model=Page[ClientOut])
async def list_clients(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[ClientOut]:
    page = await ClientService(session).list(actor, params)
    return Page[ClientOut](
        items=[ClientOut.of(c) for c in page.items], next_cursor=page.next_cursor
    )


@clients.post("", response_model=ClientOut, status_code=201)
async def create_client(body: ClientCreate, actor: ActorDep, session: SessionDep) -> ClientOut:
    return ClientOut.of(await ClientService(session).create(actor, body))


@clients.post("/discover", response_model=DiscoveryOut)
async def discover_client(body: DiscoverIn, actor: ActorDep, session: SessionDep) -> DiscoveryOut:
    """Find an MCP server's authorization server (RFC 9728, RFC 8414): a proposal for
    a client; nothing is stored, every request goes through the egress guard."""
    found = await ClientService(session).discover(actor, body.url)
    return DiscoveryOut.model_validate(found, from_attributes=True)


@clients.get("/{client_id}", response_model=ClientOut)
async def get_client(client_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> ClientOut:
    return ClientOut.of(await ClientService(session).get(actor, client_id))


@clients.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: uuid.UUID, body: ClientUpdate, actor: ActorDep, session: SessionDep
) -> ClientOut:
    return ClientOut.of(await ClientService(session).update(actor, client_id, body))


@clients.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> None:
    await ClientService(session).delete(actor, client_id, version)


@callback.get(CALLBACK_PATH.removeprefix("/api"), status_code=303, response_class=RedirectResponse)
async def oauth_callback(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    state: Annotated[str | None, Query(max_length=512)] = None,
    code: Annotated[str | None, Query(max_length=4096)] = None,
    error: Annotated[str | None, Query(max_length=256)] = None,
) -> RedirectResponse:
    """The authorization server's redirect: finish the flow, then send the browser to
    the result page (`/ai/oauth/done?status=...`)."""
    token = request.cookies.get(settings.session_cookie_name)
    auth = await AuthService(session, settings).resolve(token) if token else None
    finished = await FlowService(session).finish(auth, state, code, error)
    return RedirectResponse(finished.location(), status_code=303)
