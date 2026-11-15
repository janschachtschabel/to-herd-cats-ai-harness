"""A bearer token to the actor `/mcp` acts with (plan M8 decisions 2, 3, 5 and 6).

- One path for every caller: the header's value (empty if there is none or it is no
  bearer) is hashed and looked up once, by its hash; then one decision. An unknown,
  revoked or expired token, an agent token (not usable before task 4), and a token
  whose person is inactive or no longer holds `mcp.use` all answer the same 401
  `token.invalid`, with no extra statement in between.
- Nothing about the person's rights is kept in the token: every call builds the actor
  from the person as they are now (role, groups; memberships are read by the check
  itself), with a `ReadScope` of the token's scope ∩ the spaces whose AI policy lets
  the organisation's MCP data location receive them (never drafts), and a
  `WriteScope` of those spaces for a `write` token, of none for a `read` token.
- Each call counts against the token's limit per minute (`HERD_MCP_RATE_PER_MINUTE`,
  `core/ratelimit.py`, shared by every node): 429 `mcp.rate_limited` past it.
- `last_used_at` is set to the minute of the call, at most once a minute.

The clear text never leaves this module's arguments: it is not logged, stored or put
into an error.
"""

import hmac
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor, ReadScope, WriteScope
from app.core.clock import SYSTEM_CLOCK, Clock
from app.core.config import Settings
from app.core.errors import RateLimited, Unauthorized
from app.core.logging import bind_request_fields, log_context
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.core.ratelimit import WINDOW, RateLimiter
from app.modules.ai.models import DataLocation
from app.modules.auth.deps import SessionDep, SettingsDep
from app.modules.groups.repository import GroupRepository
from app.modules.tokens.models import AccessToken, TokenKind, TokenMode
from app.modules.tokens.repository import Found, TokenRepository
from app.modules.tokens.standing import may_use_mcp
from app.modules.tokens.values import token_digest

BEARER = "bearer "


@dataclass(frozen=True, slots=True)
class TokenActor:
    """Who calls through a token: the person's actor held to the token, the token's
    id and name (the source of what it writes), its mode, and the data location the
    AI policy treats the client as."""

    token_id: uuid.UUID
    name: str
    mode: TokenMode
    location: DataLocation
    actor: Actor


def token_invalid() -> Unauthorized:
    return Unauthorized(code="token.invalid")


class TokenResolver:
    def __init__(self, session: AsyncSession, settings: Settings, clock: Clock = SYSTEM_CLOCK):
        self.session = session
        self.settings = settings
        self.clock = clock

    async def resolve(self, authorization: str | None) -> TokenActor:
        digest = token_digest(_bearer(authorization))
        repo = TokenRepository(self.session)
        found = await repo.lookup(digest)
        now = self.clock.now()
        if found is None or not _usable(found, digest, now):
            raise token_invalid()
        token = found.token
        await repo.touch(token.org_id, token.id, now.replace(second=0, microsecond=0))
        await self._limit(token, now)  # commits, the touch with it
        actor = await self._actor(token, found)
        return TokenActor(token.id, token.name, TokenMode(token.mode), found.location, actor)

    async def _limit(self, token: AccessToken, now: datetime) -> None:
        limiter = RateLimiter(self.session, limit=self.settings.mcp_rate_per_minute)
        if await limiter.acquire(f"mcp:token:{token.id}", now) is None:
            refused = RateLimited(code="mcp.rate_limited")
            refused.retry_after = int(WINDOW.total_seconds())
            raise refused

    async def _actor(self, token: AccessToken, found: Found) -> Actor:
        principal = Principal.user(token.user_id)
        groups = await GroupRepository(self.session).group_ids_for(principal)
        spaces = await TokenRepository(self.session).scope_spaces(
            token.org_id, token.user_id, token.space_ids, found.location
        )
        read = ReadScope.of(dict.fromkeys(spaces, SpaceRole.ADMIN), drafts=False)
        write = WriteScope.of(spaces if token.mode == TokenMode.WRITE else ())
        return Actor(token.org_id, principal, found.system_role, groups, read, write)


def _bearer(authorization: str | None) -> str:
    if authorization is None or not authorization[: len(BEARER)].lower() == BEARER:
        return ""
    return authorization[len(BEARER) :].strip()


def _usable(found: Found, digest: bytes, now: datetime) -> bool:
    token = found.token
    return (
        hmac.compare_digest(token.token_hash, digest)
        and token.kind == TokenKind.PERSONAL
        and token.revoked_at is None
        and token.expires_at > now
        and may_use_mcp(found.standing)
    )


async def token_actor(
    request: Request, session: SessionDep, settings: SettingsDep
) -> AsyncIterator[TokenActor]:
    """The caller of `/mcp`, from `Authorization: Bearer`; every log line of the
    request names the person (never the token)."""
    found = await TokenResolver(session, settings).resolve(request.headers.get("authorization"))
    fields = {"org_id": str(found.actor.org_id), "actor": str(found.actor.principal)}
    bind_request_fields(**fields)
    with log_context(**fields):
        yield found


TokenActorDep = Annotated[TokenActor, Depends(token_actor, scope="function")]
