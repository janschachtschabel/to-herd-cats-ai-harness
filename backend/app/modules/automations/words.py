"""Who reads an automation's words and the names of its place (review M7, finding 2;
as the run view keeps a conversation's content to its people, M6): the instruction,
a channel's name and a ticket's number. Its owner always; anyone else who sees it
(`sight.py`) only while they may read its place now: a channel or a ticket's thread
as the conversation rules say (`ConversationReader.readable`, which notes an admin's
read of a team or personal space by admin right, `space.admin_access`); a DM never,
since only its person reads it (admins through the audited inspection). Everyone
else gets the automation `redacted`.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import NotFound
from app.modules.messaging.models import Conversation, ConversationKind
from app.modules.messaging.visibility import ConversationReader


@dataclass(slots=True)
class WordsReader:
    session: AsyncSession
    actor: Actor
    _readable: dict[uuid.UUID, bool] = field(default_factory=dict)

    async def shown(self, place: Conversation, *, owner: bool) -> bool:
        if owner:
            return True
        if place.kind == ConversationKind.DM:
            return False
        if place.id not in self._readable:
            self._readable[place.id] = await self._reads(place.id)
        return self._readable[place.id]

    async def _reads(self, conversation_id: uuid.UUID) -> bool:
        try:
            await ConversationReader(self.session).readable(self.actor, conversation_id)
        except NotFound:
            return False
        return True
