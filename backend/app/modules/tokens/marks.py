"""The AI mark of what an event's `/mcp` call caused (plan M8 decision 3): the name
of the access token the event names (`Event.token_id`, set by `outbox.through_token`),
for the timeline entries the handlers write. Events carry the id only; the name is
read here, when the entry is written."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event
from app.modules.tokens.models import AccessToken


async def via_token(session: AsyncSession, event: Event) -> str | None:
    """The name of the token whose call wrote the event (None: none did)."""
    token_id = event.token_id
    if token_id is None:
        return None
    return await _name(session, event.org_id, token_id)


async def _name(session: AsyncSession, org_id: uuid.UUID, token_id: uuid.UUID) -> str | None:
    stmt = select(AccessToken.name).where(AccessToken.org_id == org_id, AccessToken.id == token_id)
    return await session.scalar(stmt)
