"""What runs tell people besides their answers: a timeline notice where a run answers
(`run.stopped` with its stop reason, `run.refused` with why a ticket's run could not
start, `run.handover_refused`), and activity entries for messages of a run.

A notice is a system message with a key and codes for the client to word, never
content; in a thread of a channel it is a reply in that thread (the answer to a
mention goes there). Its `message.created` event carries ids only.
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.core.outbox import EventActor, emit
from app.core.principal import Principal
from app.modules.messaging import threads
from app.modules.messaging.models import Conversation, Message
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.notification_repository import NotificationRepository
from app.modules.messaging.thread_repository import ThreadRepository


async def notice(
    session: AsyncSession,
    org_id: uuid.UUID,
    agent_id: uuid.UUID,
    place: Conversation,
    client_id: uuid.UUID,
    content: dict[str, str],
    parent: Message | None = None,
) -> Message | None:
    """The notice `client_id` (None: written before), announced."""
    body = json.dumps(content)
    repo = ThreadRepository(session, org_id)
    message = await repo.add_system(place, client_id, body, utcnow(), parent=parent)
    if message is None:
        return None
    if parent is not None:
        threads.count_reply(parent, message)
        await session.flush()
    await announce(session, org_id, agent_id, message, system=True)
    return message


async def announce(
    session: AsyncSession,
    org_id: uuid.UUID,
    agent_id: uuid.UUID,
    message: Message,
    *,
    system: bool = False,
) -> None:
    """`message.created` for a message a run wrote (ids only)."""
    payload: dict[str, object] = {
        "conversation_id": str(message.conversation_id),
        "message_id": str(message.id),
        "parent_id": str(message.parent_id) if message.parent_id else None,
    }
    if system:
        payload["system"] = True
    await emit(
        session,
        type="message.created",
        actor=EventActor(org_id, Principal.agent(agent_id)),
        space_id=None,
        subject_type="message",
        subject_id=message.id,
        payload=payload,
    )


async def notify(
    session: AsyncSession,
    org_id: uuid.UUID,
    agent_id: uuid.UUID,
    message: Message,
    user_id: uuid.UUID,
    reason: NotificationReason,
) -> None:
    """An activity entry for the person about a message of a run (once)."""
    added = await NotificationRepository(session, org_id).add(message, [(user_id, reason)])
    for notification in added:
        await emit(
            session,
            type="notification.created",
            actor=EventActor(org_id, Principal.agent(agent_id)),
            space_id=None,
            subject_type="notification",
            subject_id=notification.id,
            payload={
                "notification_id": str(notification.id),
                "conversation_id": str(message.conversation_id),
                "message_id": str(message.id),
                "user_id": str(user_id),
            },
        )
