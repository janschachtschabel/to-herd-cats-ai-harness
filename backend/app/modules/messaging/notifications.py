"""Notifications from messages (spec 6.1, plan decision 3), written by the outbox
handler `notify_on_message` (`handlers.py`) in the handler's transaction:

- `mention`: everyone the message mentions (stored mentions, `mentions.py`), on
  `message.created` and on `message.updated` (a mention added by an edit). An edit
  that drops a mention withdraws that person's notification while it is unread
  (`activity.changed` to that person); a read one stays.
- `reply` (on `message.created` only): the author of the thread's top message and
  everyone who replied in the thread before this reply, unless they get a `mention`
  for it.
- `ticket_comment` (on `message.created` only, in a ticket thread): the ticket's
  assignee and reporter, unless they get a `mention` or a `reply` for it (plan M4
  decision 10).

Never to the message's author. Whether a person may see the conversation is checked
again here, at delivery time: someone who lost access since the message was written
gets nothing. A deleted message notifies nobody.

Idempotent by construction: `(user_id, message_id, reason)` is unique, so a second
delivery of the event inserts nothing and emits nothing. Each new notification is
emitted (`notification.created`, ids only, with the recipient's id: it is delivered
to that person only).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, emit
from app.modules.messaging.activity_repository import NotificationRepository
from app.modules.messaging.notification_models import Notification, NotificationReason
from app.modules.messaging.repository import readers_of
from app.modules.messaging.social_repository import MentionRepository


async def notify_on_message(session: AsyncSession, event: Event) -> None:
    """Handler of `message.created` and `message.updated` (payload `message_id`)."""
    repo = NotificationRepository(session, event.org_id)
    message = await repo.message(uuid.UUID(event.payload["message_id"]))
    if message is None or message.deleted_at is not None or message.author_id is None:
        return
    wanted: dict[uuid.UUID, NotificationReason] = {}
    mentioned = (await MentionRepository(session, event.org_id).of([message.id])).get(
        message.id, []
    )
    for user_id in mentioned:
        wanted[user_id] = NotificationReason.MENTION
    if event.type == "message.updated":
        for user_id in await repo.withdraw_mentions(message, mentioned):
            await _withdrawn(session, event, user_id)
    if event.type == "message.created" and message.parent_id is not None:
        parent = await repo.message(message.parent_id)
        if parent is not None:
            for user_id in await repo.thread_people(parent, message):
                wanted.setdefault(user_id, NotificationReason.REPLY)
    if event.type == "message.created":
        for user_id in await repo.ticket_people(message.conversation_id):
            wanted.setdefault(user_id, NotificationReason.TICKET_COMMENT)
    wanted.pop(message.author_id, None)
    readers = await readers_of(session, event.org_id, message.conversation_id, wanted)
    added = await repo.add(message, [(u, r) for u, r in wanted.items() if u in readers])
    for notification in added:
        await announce(session, event, notification)


async def _withdrawn(session: AsyncSession, event: Event, user_id: uuid.UUID) -> None:
    """The person's activity view lost an entry (ids only, for that person)."""
    await emit(
        session,
        type="activity.changed",
        actor=event.acting,
        space_id=None,
        subject_type="user",
        subject_id=user_id,
        payload={"user_id": str(user_id)},
    )


async def announce(session: AsyncSession, event: Event, notification: Notification) -> None:
    """`notification.created` for a new notification (ids only, for its person)."""
    await emit(
        session,
        type="notification.created",
        actor=event.acting,
        space_id=event.space_id,
        subject_type="notification",
        subject_id=notification.id,
        payload={
            "notification_id": str(notification.id),
            "conversation_id": str(notification.conversation_id),
            "message_id": str(notification.message_id),
            "user_id": str(notification.user_id),
        },
    )
