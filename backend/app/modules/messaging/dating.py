"""When a new message is dated (module review M8 4, K4).

A person's message in a DM is dated after the DM's fresh start ("Neu beginnen",
`agents/fresh_start.py`), whatever this node's clock says, and holds the DM's row
`FOR SHARE` until its transaction ends (`MessageRepository.fresh_start_held`): a
fresh start cannot come between its date and its commit, so the message, and the run
it queues, are either before the cut (and that run is cancelled) or after it (and that
run reads it). An agent's message and a message elsewhere are dated now."""

from datetime import datetime, timedelta

from app.core.models_base import utcnow
from app.modules.messaging.message_repository import MessageRepository
from app.modules.messaging.models import Conversation, ConversationKind

GAP = timedelta(microseconds=1)


async def dated(repo: MessageRepository, conversation: Conversation, *, person: bool) -> datetime:
    now = utcnow()
    if not person or conversation.kind != ConversationKind.DM:
        return now
    fresh = await repo.fresh_start_held(conversation.id)
    return now if fresh is None else max(now, fresh + GAP)
