"""Connector routes: the organisation's shared connectors (`ai.manage`) and each
person's own under "my connectors" (`ai.use`); without the right, 404 `ai.not_found`."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.connectors.models import ConnectorScope
from app.modules.connectors.schemas import ConnectorCreate, ConnectorOut, ConnectorUpdate
from app.modules.connectors.service import ConnectorService

shared = APIRouter(prefix="/ai/connectors", tags=["connectors"])
personal = APIRouter(prefix="/ai/my-connectors", tags=["connectors"])


def _routes(router: APIRouter, scope: ConnectorScope) -> None:
    @router.get("", response_model=Page[ConnectorOut])
    async def list_connectors(
        params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
    ) -> Page[ConnectorOut]:
        page = await ConnectorService(session).list(actor, scope, params)
        return Page[ConnectorOut](
            items=[ConnectorOut.of(c) for c in page.items], next_cursor=page.next_cursor
        )

    @router.post("", response_model=ConnectorOut, status_code=201)
    async def create_connector(
        body: ConnectorCreate, actor: ActorDep, session: SessionDep
    ) -> ConnectorOut:
        return ConnectorOut.of(await ConnectorService(session).create(actor, scope, body))

    @router.get("/{connector_id}", response_model=ConnectorOut)
    async def get_connector(
        connector_id: uuid.UUID, actor: ActorDep, session: SessionDep
    ) -> ConnectorOut:
        return ConnectorOut.of(await ConnectorService(session).get(actor, scope, connector_id))

    @router.patch("/{connector_id}", response_model=ConnectorOut)
    async def update_connector(
        connector_id: uuid.UUID, body: ConnectorUpdate, actor: ActorDep, session: SessionDep
    ) -> ConnectorOut:
        connector = await ConnectorService(session).update(actor, scope, connector_id, body)
        return ConnectorOut.of(connector)

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
