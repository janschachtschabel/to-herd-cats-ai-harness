"""Calendar changes live (plan M10 task 3a): each `calendar_event.*` outbox event
becomes one `calendar.changed` for the event's space, with the space's and the
calendar's id only (never a title, never the event's id), for the space's members
alone: never by admin power (`messaging/live_repository.space_readers`), as the
calendar lists hold no space an admin is not in (decision 3, C1)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event
from app.modules.messaging.live_events import CALENDAR, LIVE_CHANNEL, MAX_PAYLOAD_BYTES, LiveEvent

TYPES = (
    "calendar_event.created",
    "calendar_event.updated",
    "calendar_event.deleted",
    "calendar_event.responded",  # an answer changes what the event shows
)


def live_event(event: Event) -> LiveEvent | None:
    """The live event of an outbox event of the calendars; None without a space."""
    calendar_id = event.payload.get("calendar_id")
    if event.space_id is None or not isinstance(calendar_id, str):
        return None
    return LiveEvent(
        name=CALENDAR,
        org_id=event.org_id,
        conversation_id=None,
        message_id=None,
        parent_id=None,
        user_id=None,
        space_id=event.space_id,
        calendar_id=uuid.UUID(calendar_id),
    )


async def publish(session: AsyncSession, event: Event) -> None:
    """Outbox handler: NOTIFY every API process (sent when the lane commits). A second
    delivery notifies again, which costs a client one reload."""
    live = live_event(event)
    if live is None:
        return
    payload = live.payload()
    if len(payload.encode()) > MAX_PAYLOAD_BYTES:  # ids only: cannot happen
        raise ValueError("live payload too large")
    await session.execute(select(func.pg_notify(LIVE_CHANNEL, payload)))
