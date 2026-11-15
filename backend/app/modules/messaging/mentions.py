"""Mentions (plan decision 4, review focus 4).

The client sends the ids it mentions next to the text (`@[Name](user:<id>)` in
`body_md` is for display only). At most 50 per message. Only people who may see the
conversation at that moment are stored (and later notified); every other id asked
for comes back in `not_notified`, in the order asked. Unknown ids, ids of another
organisation, of deactivated people and of people without access are all simply
"not notified": the answer cannot tell them apart, so a mention reveals nothing
about who belongs to which space.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailed
from app.modules.messaging.models import Conversation
from app.modules.messaging.repository import readers_of
from app.modules.messaging.social_repository import MentionRepository

MAX_MENTIONS = 50


def asked(mentions: Iterable[uuid.UUID]) -> list[uuid.UUID]:
    """The ids asked for, each once, in their order (422 beyond the limit)."""
    ids = list(dict.fromkeys(mentions))
    if len(ids) > MAX_MENTIONS:
        raise ValidationFailed(f"at most {MAX_MENTIONS} mentions", code="message.too_many_mentions")
    return ids


async def mention(
    session: AsyncSession,
    org_id: uuid.UUID,
    conversation: Conversation,
    message_id: uuid.UUID,
    ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    """The message mentions those of `ids` who may see the conversation (and nobody
    else, replacing what it mentioned before); the others are returned."""
    readers = await readers_of(session, org_id, conversation.id, ids)
    await MentionRepository(session, org_id).replace(message_id, [i for i in ids if i in readers])
    return [i for i in ids if i not in readers]


async def not_mentioned(
    session: AsyncSession, org_id: uuid.UUID, message_id: uuid.UUID, ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    """Those of `ids` the stored message does not mention (a resend's answer)."""
    stored = set((await MentionRepository(session, org_id).of([message_id]))[message_id])
    return [i for i in ids if i not in stored]
