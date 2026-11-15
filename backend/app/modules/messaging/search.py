"""Search in messages (plan M3 task 9), for the search service (`modules/search`).

The actor's view of the conversations (`ConversationReader.scope`) is the whole
filter: the statement (`search_repository.py`) keeps the messages of the
conversations `visible_conversations` lets through, for every kind at once. An
admin's DM inspection is not part of that view, so it never opens the search.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.modules.messaging.search_repository import MessageHit, MessageSearchRepository
from app.modules.messaging.visibility import ConversationReader

__all__ = ["MessageHit", "MessageSearch"]


class MessageSearch:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find(
        self,
        actor: Actor,
        q: str,
        *,
        space_id: uuid.UUID | None,
        after: tuple[float, uuid.UUID] | None,
        limit: int,
    ) -> list[MessageHit]:
        """Best first, below `after` (score, id); with `space_id`, only the space's
        channels and page threads."""
        scope = ConversationReader(self.session).scope(actor)
        return await MessageSearchRepository(self.session, scope).messages(
            q, space_id=space_id, after=after, limit=limit
        )
