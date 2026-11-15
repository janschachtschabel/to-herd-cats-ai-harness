"""Connector routes: the organisation's shared connectors (`ai.manage`) and each
person's own under "my connectors" (`ai.use`); without the right, 404 `ai.not_found`."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.access import Actor
from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, AuthDep, SessionDep
from app.modules.connectors.models import Connector, ConnectorScope
from app.modules.connectors.schemas import (
    ConnectorCreate,
    ConnectorOut,
    ConnectorUpdate,
    VersionIn,
)
from app.modules.connectors.service import ConnectorService
from app.modules.oauth.flow import FlowService
from app.modules.oauth.schemas import AuthorizeOut

shared = APIRouter(prefix="/ai/connectors", tags=["connectors"])
personal = APIRouter(prefix="/ai/my-connectors", tags=["connectors"])


async def _out(session: SessionDep, actor: Actor, connector: Connector) -> ConnectorOut:
    urls = await ConnectorService(session).urls(actor, [connector])
    return ConnectorOut.of(connector, urls)


def _routes(router: APIRouter, scope: ConnectorScope) -> None:
    @router.get("", response_model=Page[ConnectorOut])
    async def list_connectors(
        params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
    ) -> Page[ConnectorOut]:
        service = ConnectorService(session)
        page = await service.list(actor, scope, params)
        urls = await service.urls(actor, page.items)
        return Page[ConnectorOut](
            items=[ConnectorOut.of(c, urls) for c in page.items], next_cursor=page.next_cursor
        )

    @router.post("", response_model=ConnectorOut, status_code=201)
    async def create_connector(
        body: ConnectorCreate, actor: ActorDep, session: SessionDep
    ) -> ConnectorOut:
        return await _out(
            session, actor, await ConnectorService(session).create(actor, scope, body)
        )

    @router.get("/{connector_id}", response_model=ConnectorOut)
    async def get_connector(
        connector_id: uuid.UUID, actor: ActorDep, session: SessionDep
    ) -> ConnectorOut:
        connector = await ConnectorService(session).get(actor, scope, connector_id)
        return await _out(session, actor, connector)

    @router.patch("/{connector_id}", response_model=ConnectorOut)
    async def update_connector(
        connector_id: uuid.UUID, body: ConnectorUpdate, actor: ActorDep, session: SessionDep
    ) -> ConnectorOut:
        connector = await ConnectorService(session).update(actor, scope, connector_id, body)
        return await _out(session, actor, connector)

    @router.post("/{connector_id}/authorize", response_model=AuthorizeOut)
    async def authorize_connector(
        connector_id: uuid.UUID, ctx: AuthDep, actor: ActorDep, session: SessionDep
    ) -> AuthorizeOut:
        """OAuth: where the browser goes to approve; it comes back to the callback."""
        url = await FlowService(session).start(actor, ctx.session_id, scope, connector_id)
        return AuthorizeOut(authorization_url=url)

    @router.post("/{connector_id}/disconnect", response_model=ConnectorOut)
    async def disconnect_connector(
        connector_id: uuid.UUID, body: VersionIn, actor: ActorDep, session: SessionDep
    ) -> ConnectorOut:
        """OAuth: forget the tokens and revoke them at the provider."""
        connector = await FlowService(session).disconnect(actor, scope, connector_id, body.version)
        return await _out(session, actor, connector)

    @router.delete("/{connector_id}", status_code=204)
    async def delete_connector(
        connector_id: uuid.UUID,
        version: Annotated[int, Query()],
        actor: ActorDep,
        session: SessionDep,
    ) -> None:
        await ConnectorService(session).delete(actor, scope, connector_id, version)


_routes(shared, ConnectorScope.SHARED)
_routes(personal, ConnectorScope.PERSONAL)
