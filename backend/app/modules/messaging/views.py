"""Messages as their reader is shown them: with whom they mention and their reactions
summed up (`mine` from the reader's side). For messages the reader has been allowed
to see; two queries for a whole page."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.modules.messaging.models import Message
from app.modules.messaging.social_repository import (
    MentionRepository,
    ReactionRepository,
    ReactionSummary,
)


@dataclass(frozen=True, slots=True)
class MessageView:
    message: Message
    mentions: list[uuid.UUID]
    reactions: list[ReactionSummary]


async def message_views(
    session: AsyncSession, actor: Actor, messages: Sequence[Message]
) -> list[MessageView]:
    ids = [m.id for m in messages]
    mentions = await MentionRepository(session, actor.org_id).of(ids)
    reactions = await ReactionRepository(session, actor.org_id).summaries(ids, actor.principal.id)
    return [MessageView(m, mentions.get(m.id, []), reactions.get(m.id, [])) for m in messages]
