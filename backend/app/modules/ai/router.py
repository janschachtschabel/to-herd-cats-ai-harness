"""AI connection routes (`ai.manage`; anyone else: 404 `ai.not_found`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.ai.connections import ConnectionService
from app.modules.ai.schemas import (
    CheckIn,
    CheckOut,
    ConnectionCreate,
    ConnectionOut,
    ConnectionUpdate,
    VersionIn,
)
from app.modules.auth.deps import ActorDep, SessionDep

connections = APIRouter(prefix="/ai/connections", tags=["ai"])


@connections.get("", response_model=Page[ConnectionOut])
async def list_connections(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[ConnectionOut]:
    page = await ConnectionService(session).list(actor, params)
    return Page[ConnectionOut](
        items=[ConnectionOut.of(c) for c in page.items], next_cursor=page.next_cursor
    )


@connections.post("", response_model=ConnectionOut, status_code=201)
async def create_connection(
    body: ConnectionCreate, actor: ActorDep, session: SessionDep
) -> ConnectionOut:
    return ConnectionOut.of(await ConnectionService(session).create(actor, body))


@connections.get("/{connection_id}", response_model=ConnectionOut)
async def get_connection(
    connection_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> ConnectionOut:
    return ConnectionOut.of(await ConnectionService(session).get(actor, connection_id))


@connections.patch("/{connection_id}", response_model=ConnectionOut)
async def update_connection(
    connection_id: uuid.UUID, body: ConnectionUpdate, actor: ActorDep, session: SessionDep
) -> ConnectionOut:
    return ConnectionOut.of(await ConnectionService(session).update(actor, connection_id, body))


@connections.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> None:
    """409 `ai.connection_in_use` while an assignment uses it."""
    await ConnectionService(session).delete(actor, connection_id, version)


@connections.post("/{connection_id}/test", response_model=CheckOut)
async def test_connection(
    connection_id: uuid.UUID, body: CheckIn, actor: ActorDep, session: SessionDep
) -> CheckOut:
    """One small call to the provider; the outcome as a state, never its answer."""
    status, model, duration_ms = await ConnectionService(session).check(
        actor, connection_id, body.model
    )
    return CheckOut(status=status, model=model, duration_ms=duration_ms)


@connections.post("/{connection_id}/models", response_model=ConnectionOut)
async def fetch_models(
    connection_id: uuid.UUID, body: VersionIn, actor: ActorDep, session: SessionDep
) -> ConnectionOut:
    """Read the models from the provider's `/models`; 502 `ai.provider_failed` with
    `details.status` when it does not answer with a list."""
    connection = await ConnectionService(session).fetch_models(actor, connection_id, body.version)
    return ConnectionOut.of(connection)
