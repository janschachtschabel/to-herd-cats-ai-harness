"""Access tokens (plan M8 decisions 2 and 5): one's own with `mcp.use`, everyone's
for the AI administration.

- Without `mcp.use` (switch off, a guest, an inactive person) the own routes answer
  404 `token.not_found`, as for an unknown id: there is nothing to see.
- Creating: a name, `read` or `write`, a scope (spaces the person reads now, else
  422 `token.space_invalid`, the same for unknown and unreadable ones; or all the
  person's spaces), and an expiry of 1 to 365 days. The clear text is returned this
  once; the row keeps its hash.
- Revoking is idempotent: a second revocation changes nothing and records nothing.
  Someone else's token answers like an unknown one.
- `ai.manage` lists every token of the organisation (metadata only) and revokes any;
  without it, 404 `ai.not_found`.
- The audit log names what changed (kind, mode, scope size, expiry), never a hash or
  clear text.
"""

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.clock import SYSTEM_CLOCK, Clock
from app.core.errors import NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.ai.access import require_ai
from app.modules.audit.recorder import record
from app.modules.tokens.models import AccessToken, TokenKind, TokenMode
from app.modules.tokens.repository import Listed, TokenRepository
from app.modules.tokens.values import new_secret, token_digest

TARGET = "access_token"


def token_not_found() -> NotFound:
    return NotFound(code="token.not_found")


class TokenService:
    def __init__(self, session: AsyncSession, clock: Clock = SYSTEM_CLOCK) -> None:
        self.session = session
        self.clock = clock
        self.repo = TokenRepository(session)

    async def create(
        self,
        actor: Actor,
        name: str,
        mode: TokenMode,
        expires_in_days: int,
        space_ids: list[uuid.UUID] | None,
    ) -> tuple[AccessToken, str]:
        await self._require_mcp(actor)
        scope = list(dict.fromkeys(space_ids)) if space_ids is not None else None
        for space_id in scope or ():
            if not await can(self.session, actor, Action.SPACE_READ, space_id):
                raise ValidationFailed(code="token.space_invalid")
        secret = new_secret(TokenKind.PERSONAL)
        now = self.clock.now()
        token = await self.repo.add(
            AccessToken(
                org_id=actor.org_id,
                kind=TokenKind.PERSONAL,
                user_id=actor.principal.id,
                name=name,
                token_hash=token_digest(secret),
                space_ids=scope,
                mode=mode,
                created_at=now,
                expires_at=now + timedelta(days=expires_in_days),
            )
        )
        await self._audit(actor, "access_token.created", token, details_of(token))
        return token, secret

    async def mine(self, actor: Actor, params: PageParams) -> Page[AccessToken]:
        await self._require_mcp(actor)
        before = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo.own_page(actor.org_id, actor.principal.id, before, params.limit + 1)
        return id_page(rows, params.limit, lambda t: t.id)

    async def own(self, actor: Actor, token_id: uuid.UUID) -> AccessToken:
        """One of the actor's own tokens (404 for anyone else's, or without `mcp.use`)."""
        await self._require_mcp(actor)
        token = await self.repo.get(actor.org_id, token_id, actor.principal.id)
        if token is None:
            raise token_not_found()
        return token

    async def revoke_mine(self, actor: Actor, token_id: uuid.UUID) -> None:
        await self._revoke(actor, await self.own(actor, token_id), {})

    async def everyone(self, actor: Actor, params: PageParams) -> Page[Listed]:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        before = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo.all_page(actor.org_id, before, params.limit + 1)
        return id_page(rows, params.limit, lambda listed: listed.token.id)

    async def any_of_org(self, actor: Actor, token_id: uuid.UUID) -> AccessToken:
        """Any token of the organisation, for `ai.manage` (404 `ai.not_found` without)."""
        await require_ai(self.session, actor, Action.AI_MANAGE)
        token = await self.repo.get(actor.org_id, token_id)
        if token is None:
            raise token_not_found()
        return token

    async def revoke_any(self, actor: Actor, token_id: uuid.UUID) -> None:
        token = await self.any_of_org(actor, token_id)
        await self._revoke(actor, token, {"user_id": str(token.user_id)})

    async def _revoke(self, actor: Actor, token: AccessToken, details: dict[str, Any]) -> None:
        if await self.repo.revoke(actor.org_id, token.id, self.clock.now()):
            await self._audit(actor, "access_token.revoked", token, details)

    async def _require_mcp(self, actor: Actor) -> None:
        if not await can(self.session, actor, Action.MCP_USE):
            raise token_not_found()

    async def _audit(
        self, actor: Actor, action: str, token: AccessToken, details: dict[str, Any]
    ) -> None:
        await record(self.session, actor, action, TARGET, token.id, details or None)


def details_of(token: AccessToken) -> dict[str, Any]:
    """What the audit says of a new token (never its hash or clear text)."""
    return {
        "kind": token.kind,
        "mode": token.mode,
        "spaces": "all" if token.space_ids is None else len(token.space_ids),
        "expires_at": token.expires_at.isoformat(),
    }
