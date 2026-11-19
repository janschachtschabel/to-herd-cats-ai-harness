"""What invitations tell (plan M10 decision 7): notifications in the activity view, and
nothing in any channel or direct message (as with tickets). Written by the outbox
handlers in the delivery's transaction, idempotent:

- `on_invited` (`calendar_event.invited`, one per person): `invitation` for the person,
  if she is still invited to the event row (a tombstone too: it tells her it was
  deleted).
- `on_responded` (`calendar_event.responded`): `invite_reply` for the event's
  organiser when an attendee declined or answered "maybe", never for her own answer
  and never for an agent organiser.

`tell` keeps one notification per person, event and reason: a further change renews it
(the old row goes, a new one comes: unread, on top) when the stored one is older than
the change's outbox event, so delivering an event twice leaves one, and a read one
stays read (review M10 task 4, R4-2). Each new one is announced
(`notification.created`, ids only, for that person alone).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event
from app.core.principal import Principal, PrincipalType
from app.modules.calendars.attendee_models import Response
from app.modules.calendars.attendee_repository import AttendeeRepository
from app.modules.calendars.event_repository import EventRepository
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.notification_repository import NotificationRepository
from app.modules.messaging.notifications import announce

TOLD_OF = frozenset({Response.DECLINED, Response.TENTATIVE})


async def tell(
    session: AsyncSession,
    cause: Event,
    *,
    user_id: uuid.UUID,
    event_id: uuid.UUID,
    reason: NotificationReason,
) -> None:
    """The one notification of the person about the event for `reason`, renewed
    unless it is not older than `cause`."""
    renewed = await NotificationRepository(session, cause.org_id).renew_about_event(
        user_id, event_id, reason, cause.created_at
    )
    if renewed is not None:
        await announce(session, cause, renewed)


async def on_invited(session: AsyncSession, event: Event) -> None:
    user_id = uuid.UUID(event.payload["user_id"])
    repo = AttendeeRepository(session, event.org_id)
    if await repo.invites(event.subject_id, Principal.user(user_id)):
        await tell(
            session,
            event,
            user_id=user_id,
            event_id=event.subject_id,
            reason=NotificationReason.INVITATION,
        )


async def on_responded(session: AsyncSession, event: Event) -> None:
    if event.payload.get("response") not in TOLD_OF:
        return
    organiser = await EventRepository(session, event.org_id).organiser(event.subject_id)
    if organiser is None or organiser.type != PrincipalType.USER or organiser == event.actor:
        return
    await tell(
        session,
        event,
        user_id=organiser.id,
        event_id=event.subject_id,
        reason=NotificationReason.INVITE_REPLY,
    )
