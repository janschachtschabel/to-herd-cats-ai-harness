"""External MCP server routes (`ai.manage`; anyone else: 404 `ai.not_found`), and the
personal servers for "my connections" (`ai.use`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.mcp_servers.schemas import (
    CreatedServerOut,
    PersonalServerOut,
    RefreshOut,
    ServerCreate,
    ServerOut,
    ServerUpdate,
    TestOut,
    ToolClassify,
    ToolOut,
    ToolVersionIn,
)
from app.modules.mcp_servers.service import ServerService
from app.modules.mcp_servers.tools import ToolService

servers = APIRouter(prefix="/ai/mcp-servers", tags=["mcp"])
personal = APIRouter(prefix="/ai/my-mcp-servers", tags=["mcp"])


@servers.get("", response_model=Page[ServerOut])
async def list_servers(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[ServerOut]:
    page = await ServerService(session).list(actor, params)
    return Page[ServerOut](
        items=[ServerOut.of(s) for s in page.items], next_cursor=page.next_cursor
    )


@servers.post("", response_model=CreatedServerOut, status_code=201)
async def create_server(
    body: ServerCreate, actor: ActorDep, session: SessionDep
) -> CreatedServerOut:
    """Saves the server, then reads its tool list; `refresh` says how that went."""
    server, refresh = await ServerService(session).create(actor, body)
    return CreatedServerOut(**ServerOut.of(server).model_dump(), refresh=refresh)


@servers.get("/{server_id}", response_model=ServerOut)
async def get_server(server_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> ServerOut:
    return ServerOut.of(await ServerService(session).get(actor, server_id))


@servers.patch("/{server_id}", response_model=ServerOut)
async def update_server(
    server_id: uuid.UUID, body: ServerUpdate, actor: ActorDep, session: SessionDep
) -> ServerOut:
    return ServerOut.of(await ServerService(session).update(actor, server_id, body))


@servers.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> None:
    await ServerService(session).delete(actor, server_id, version)


@servers.post("/{server_id}/refresh", response_model=RefreshOut)
async def refresh_tools(server_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> RefreshOut:
    """Read the tool list again; a failure is a state, never the server's answer."""
    return await ToolService(session).refresh(actor, server_id)


@servers.post("/{server_id}/test", response_model=TestOut)
async def test_server(server_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> TestOut:
    """Connect and list the tools; nothing is stored."""
    return await ToolService(session).test(actor, server_id)


@servers.get("/{server_id}/tools", response_model=Page[ToolOut])
async def list_tools(
    server_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[ToolOut]:
    page = await ToolService(session).list(actor, server_id, params)
    return Page[ToolOut](items=[ToolOut.of(t) for t in page.items], next_cursor=page.next_cursor)


@servers.patch("/{server_id}/tools/{tool_id}", response_model=ToolOut)
async def classify_tool(
    server_id: uuid.UUID,
    tool_id: uuid.UUID,
    body: ToolClassify,
    actor: ActorDep,
    session: SessionDep,
) -> ToolOut:
    return ToolOut.of(await ToolService(session).classify(actor, server_id, tool_id, body))


@servers.post("/{server_id}/tools/{tool_id}/approve", response_model=ToolOut)
async def approve_tool(
    server_id: uuid.UUID,
    tool_id: uuid.UUID,
    body: ToolVersionIn,
    actor: ActorDep,
    session: SessionDep,
) -> ToolOut:
    """Approve exactly the tool as last read (its fingerprint)."""
    tool = await ToolService(session).approve(actor, server_id, tool_id, body.version)
    return ToolOut.of(tool)


@servers.post("/{server_id}/tools/{tool_id}/block", response_model=ToolOut)
async def block_tool(
    server_id: uuid.UUID,
    tool_id: uuid.UUID,
    body: ToolVersionIn,
    actor: ActorDep,
    session: SessionDep,
) -> ToolOut:
    tool = await ToolService(session).block(actor, server_id, tool_id, body.version)
    return ToolOut.of(tool)


@personal.get("", response_model=Page[PersonalServerOut])
async def list_personal_servers(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[PersonalServerOut]:
    return await ServerService(session).personal(actor, params)
