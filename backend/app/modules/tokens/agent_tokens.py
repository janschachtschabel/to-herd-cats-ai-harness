"""An external agent's tokens (plan M8 decisions 2 and 11): issued, listed and revoked
by whoever manages the agent (`agent.manage`; anyone else 404 `agent.not_found`, as
for an unknown agent).

- Only an external agent has tokens (422 `token.agent_not_external`), and only while
  its responsible person holds `mcp.use` (422 `token.responsible_without_mcp`): the
  token acts with that person's rights (its `user_id`), held to the agent's roles.
- The scope names spaces the agent may read (a membership or an open space), else
  422 `token.space_invalid`, the same for unknown ones; left out: all of them.
- The clear text (`herd_agt_…`) is returned this once. Revoking is idempotent; a
  token of another agent answers like an unknown one (404 `token.not_found`).
- The audit names the agent, kind, mode, scope size and expiry, never a hash or the
  clear text (`access_token.created`, `access_token.revoked`).
"""

import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.clock import SYSTEM_CLOCK, Clock
from app.core.errors import ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.agents.models import Agent
from app.modules.agents.repository import AgentRepository
from app.modules.agents.service import AgentService
from app.modules.audit.recorder import record
from app.modules.mcp_tools.models import McpCall
from app.modules.mcp_tools.repository import McpCallRepository
from app.modules.tokens.models import AccessToken, TokenKind, TokenMode
from app.modules.tokens.repository import TokenRepository
from app.modules.tokens.service import TARGET, details_of, token_not_found
from app.modules.tokens.standing import holds_mcp_use
from app.modules.tokens.values import new_secret, token_digest


class AgentTokenService:
    def __init__(self, session: AsyncSession, clock: Clock = SYSTEM_CLOCK) -> None:
        self.session = session
        self.clock = clock
        self.repo = TokenRepository(session)

    async def create(
        self,
        actor: Actor,
        agent_id: uuid.UUID,
        name: str,
        mode: TokenMode,
        expires_in_days: int,
        space_ids: list[uuid.UUID] | None,
    ) -> tuple[AccessToken, str]:
        agent = await AgentService(self.session).get(actor, agent_id)
        if not agent.external:
            raise ValidationFailed(code="token.agent_not_external")
        if not await holds_mcp_use(self.session, actor.org_id, agent.responsible_user_id):
            raise ValidationFailed(code="token.responsible_without_mcp")
        scope = list(dict.fromkeys(space_ids)) if space_ids is not None else None
        readable = await AgentRepository(self.session, actor.org_id).roles(agent.id)
        if any(space_id not in readable for space_id in scope or ()):
            raise ValidationFailed(code="token.space_invalid")
        secret = new_secret(TokenKind.AGENT)
        now = self.clock.now()
        token = await self.repo.add(
            AccessToken(
                org_id=actor.org_id,
                kind=TokenKind.AGENT,
                user_id=agent.responsible_user_id,
                agent_id=agent.id,
                name=name,
                token_hash=token_digest(secret),
                space_ids=scope,
                mode=mode,
                created_at=now,
                expires_at=now + timedelta(days=expires_in_days),
            )
        )
        details = {**details_of(token), "agent_id": str(agent.id)}
        await record(self.session, actor, "access_token.created", TARGET, token.id, details)
        return token, secret

    async def list(
        self, actor: Actor, agent_id: uuid.UUID, params: PageParams
    ) -> Page[AccessToken]:
        agent = await self._agent(actor, agent_id)
        before = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo.agent_page(actor.org_id, agent.id, before, params.limit + 1)
        return id_page(rows, params.limit, lambda t: t.id)

    async def revoke(self, actor: Actor, agent_id: uuid.UUID, token_id: uuid.UUID) -> None:
        token = await self._token(actor, agent_id, token_id)
        if await self.repo.revoke(actor.org_id, token.id, self.clock.now()):
            details = {"agent_id": str(agent_id)}
            await record(self.session, actor, "access_token.revoked", TARGET, token.id, details)

    async def calls(
        self, actor: Actor, agent_id: uuid.UUID, token_id: uuid.UUID, params: PageParams
    ) -> Page[McpCall]:
        """The token's tool calls through `/mcp`, newest first (the agent's activity)."""
        token = await self._token(actor, agent_id, token_id)
        before = decode_id_cursor(params.cursor) if params.cursor else None
        repo = McpCallRepository(self.session, actor.org_id)
        rows = await repo.page(token.id, before, params.limit + 1)
        return id_page(rows, params.limit, lambda call: call.id)

    async def _agent(self, actor: Actor, agent_id: uuid.UUID) -> Agent:
        return await AgentService(self.session).get(actor, agent_id)

    async def _token(self, actor: Actor, agent_id: uuid.UUID, token_id: uuid.UUID) -> AccessToken:
        agent = await self._agent(actor, agent_id)
        token = await self.repo.of_agent(actor.org_id, agent.id, token_id)
        if token is None:
            raise token_not_found()
        return token
