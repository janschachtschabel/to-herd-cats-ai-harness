"""Access token routes: one's own (`/tokens`, `mcp.use`; otherwise 404
`token.not_found`), the AI administration's (`/ai/mcp`, `ai.manage`; otherwise
404 `ai.not_found`) and an external agent's (`/agents/{id}/tokens`, `agent.manage`;
otherwise 404 `agent.not_found`). These are session routes; `/mcp` itself takes the token
(`resolve.TokenActorDep`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.mcp_tools.models import McpCall
from app.modules.mcp_tools.schemas import McpCallOut
from app.modules.mcp_tools.usage import McpUsageService
from app.modules.tokens.agent_tokens import AgentTokenService
from app.modules.tokens.schemas import (
    AdminTokenOut,
    McpSettingsIn,
    McpSettingsOut,
    TokenCreatedOut,
    TokenIn,
    TokenOut,
)
from app.modules.tokens.service import TokenService
from app.modules.tokens.settings import McpSettings, McpSettingsService

tokens = APIRouter(prefix="/tokens", tags=["tokens"])
mcp_admin = APIRouter(prefix="/ai/mcp", tags=["ai"])
agent_tokens = APIRouter(prefix="/agents/{agent_id}/tokens", tags=["agents"])


@tokens.get("", response_model=Page[TokenOut])
async def list_my_tokens(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[TokenOut]:
    """My tokens, newest first (revoked and expired ones too)."""
    page = await TokenService(session).mine(actor, params)
    return Page[TokenOut](
        items=[TokenOut.model_validate(t) for t in page.items], next_cursor=page.next_cursor
    )


@tokens.post("", response_model=TokenCreatedOut, status_code=201)
async def create_token(body: TokenIn, actor: ActorDep, session: SessionDep) -> TokenCreatedOut:
    """A new token; `secret` is its clear text, shown this once."""
    token, secret = await TokenService(session).create(
        actor, body.name, body.mode, body.expires_in_days, body.space_ids
    )
    return TokenCreatedOut.of(token, secret)


@tokens.get("/{token_id}/calls", response_model=Page[McpCallOut])
async def list_my_token_calls(
    token_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[McpCallOut]:
    """The token's tool calls through `/mcp`, newest first (its usage)."""
    page = await McpUsageService(session).mine(actor, token_id, params)
    return _calls(page)


@tokens.delete("/{token_id}", status_code=204)
async def revoke_my_token(token_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await TokenService(session).revoke_mine(actor, token_id)


@mcp_admin.get("", response_model=McpSettingsOut)
async def get_mcp_settings(actor: ActorDep, session: SessionDep) -> McpSettingsOut:
    return _settings(await McpSettingsService(session).get(actor))


@mcp_admin.put("", response_model=McpSettingsOut)
async def set_mcp_settings(
    body: McpSettingsIn, actor: ActorDep, session: SessionDep
) -> McpSettingsOut:
    """The switch for `mcp.use` and the data location, with the version read (409)."""
    service = McpSettingsService(session)
    return _settings(await service.set(actor, body.enabled, body.data_location, body.version))


@mcp_admin.get("/tokens", response_model=Page[AdminTokenOut])
async def list_all_tokens(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[AdminTokenOut]:
    """Every token of the organisation, newest first: metadata only."""
    page = await TokenService(session).everyone(actor, params)
    return Page[AdminTokenOut](
        items=[AdminTokenOut.of(t) for t in page.items], next_cursor=page.next_cursor
    )


@mcp_admin.get("/tokens/{token_id}/calls", response_model=Page[McpCallOut])
async def list_any_token_calls(
    token_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[McpCallOut]:
    """Any token's tool calls through `/mcp`, newest first: metadata only."""
    page = await McpUsageService(session).any(actor, token_id, params)
    return _calls(page)


@mcp_admin.delete("/tokens/{token_id}", status_code=204)
async def revoke_any_token(token_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await TokenService(session).revoke_any(actor, token_id)


@agent_tokens.get("", response_model=Page[TokenOut])
async def list_agent_tokens(
    agent_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[TokenOut]:
    """An external agent's tokens, newest first (`agent.manage`)."""
    page = await AgentTokenService(session).list(actor, agent_id, params)
    return Page[TokenOut](
        items=[TokenOut.model_validate(t) for t in page.items], next_cursor=page.next_cursor
    )


@agent_tokens.post("", response_model=TokenCreatedOut, status_code=201)
async def create_agent_token(
    agent_id: uuid.UUID, body: TokenIn, actor: ActorDep, session: SessionDep
) -> TokenCreatedOut:
    """A token for an external agent (`herd_agt_…`); `secret` is shown this once."""
    token, secret = await AgentTokenService(session).create(
        actor, agent_id, body.name, body.mode, body.expires_in_days, body.space_ids
    )
    return TokenCreatedOut.of(token, secret)


@agent_tokens.get("/{token_id}/calls", response_model=Page[McpCallOut])
async def list_agent_token_calls(
    agent_id: uuid.UUID,
    token_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[McpCallOut]:
    """The agent token's tool calls through `/mcp`, newest first."""
    return _calls(await AgentTokenService(session).calls(actor, agent_id, token_id, params))


@agent_tokens.delete("/{token_id}", status_code=204)
async def revoke_agent_token(
    agent_id: uuid.UUID, token_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> None:
    await AgentTokenService(session).revoke(actor, agent_id, token_id)


def _calls(page: Page[McpCall]) -> Page[McpCallOut]:
    return Page[McpCallOut](
        items=[McpCallOut.model_validate(c) for c in page.items], next_cursor=page.next_cursor
    )


def _settings(found: McpSettings) -> McpSettingsOut:
    return McpSettingsOut(
        enabled=found.enabled, data_location=found.data_location, version=found.version
    )
