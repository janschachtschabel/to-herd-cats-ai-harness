"""The worker's side of live delivery (spec 6.4, `live_events.py`): an outbox event as
the `LiveEvent` it is delivered as, and the outbox handler that NOTIFYs it."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event
from app.modules.messaging.live_events import (
    AUTOMATION,
    FOR_ONE_PERSON,
    LIVE_CHANNEL,
    LIVE_TYPES,
    MAX_PAYLOAD_BYTES,
    PROPOSAL_TYPES,
    SKILL_PROPOSAL,
    SPACE_TYPES,
    TICKET_TYPES,
    LiveEvent,
)


def of_event(event: Event) -> LiveEvent | None:
    """The live event of an outbox event; None for types that are not delivered live."""
    name = LIVE_TYPES.get(event.type)
    if name is None:
        return None
    payload = event.payload
    ticket = event.type in TICKET_TYPES
    if event.type in SPACE_TYPES:
        if event.space_id is None:
            return None
        return LiveEvent(
            name=name,
            org_id=event.org_id,
            conversation_id=None,
            message_id=None,
            parent_id=None,
            user_id=None,
            space_id=event.space_id,
            sprint_id=_uuid(payload.get("sprint_id")),
            proposal_id=_uuid(payload.get("proposal_id")),
            author_id=_uuid(payload.get("author_id")) if event.type in PROPOSAL_TYPES else None,
        )
    run = event.type == "run.progress"
    step = payload.get("step")
    automation = name == AUTOMATION
    return LiveEvent(
        name=name,
        org_id=event.org_id,
        conversation_id=_uuid(payload.get("conversation_id")),
        message_id=_uuid(payload.get("message_id")),
        parent_id=_uuid(payload.get("parent_id")),
        user_id=_uuid(payload.get("user_id")) if event.type in FOR_ONE_PERSON else None,
        ticket_id=_uuid(payload.get("ticket_id")) if ticket else None,
        space_id=event.space_id if ticket or automation else None,
        run_id=_uuid(payload.get("run_id")) if run else None,
        step=step if run and isinstance(step, int) else None,
        proposal_id=_uuid(payload.get("proposal_id")) if name == SKILL_PROPOSAL else None,
        automation_id=_uuid(payload.get("automation_id")) if automation else None,
    )


def _uuid(value: object) -> uuid.UUID | None:
    return uuid.UUID(value) if isinstance(value, str) else None


async def publish_live(session: AsyncSession, event: Event) -> None:
    """Outbox handler: NOTIFY every API process. A second delivery notifies again,
    which costs a client one reload of what it shows, nothing more."""
    live = of_event(event)
    if live is None:
        return
    payload = live.payload()
    if len(payload.encode()) > MAX_PAYLOAD_BYTES:  # ids only: cannot happen
        raise ValueError("live payload too large")
    await session.execute(select(func.pg_notify(LIVE_CHANNEL, payload)))
