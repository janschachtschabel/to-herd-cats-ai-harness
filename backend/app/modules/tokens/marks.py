"""The AI mark of what an event's `/mcp` call caused (plan M8 decision 3): the name
of the access token the event names (`Event.token_id`, set by `outbox.through_token`),
for the timeline entries the handlers write. Events carry the id only; the name is
read here, when the entry is written."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event
from app.modules.tokens.repository import TokenRepository


async def via_token(session: AsyncSession, event: Event) -> str | None:
    """The name of the token whose call wrote the event (None: none did)."""
    if event.token_id is None:
        return None
    return await TokenRepository(session).name_of(event.org_id, event.token_id)
