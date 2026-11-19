"""Routes of invitations (plan M10 task 4): an event's attendees and one's answer. The
window's `mine=true` ("my events") is in `event_router.py`."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.calendars.invitation_schemas import (
    AttendeeOut,
    AttendeesIn,
    AttendeesSetOut,
    ResponseIn,
)
from app.modules.calendars.invitations import InvitationService

invitations = APIRouter(prefix="/events/{event_id}", tags=["calendar events"])


@invitations.get("/attendees", response_model=Page[AttendeeOut])
async def list_attendees(
    event_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[AttendeeOut]:
    """The event's attendees (full sight of the event; 403 `event.private` with "busy"
    sight)."""
    _, page = await InvitationService(session).attendees(actor, event_id, params)
    return Page[AttendeeOut](
        items=[AttendeeOut.listed(row) for row in page.items], next_cursor=page.next_cursor
    )


@invitations.put("/attendees", response_model=AttendeesSetOut)
async def set_attendees(
    event_id: uuid.UUID, body: AttendeesIn, actor: ActorDep, session: SessionDep
) -> AttendeesSetOut:
    """Sets the event's attendees (`calendar.write` and full sight, at the version
    read: 409 `event.version_conflict`); on a series, who comes and who goes reaches
    its overrides too. New people are told in their activity view."""
    event = await InvitationService(session).set_attendees(
        actor, event_id, [a.invitee() for a in body.attendees], version=body.version
    )
    return AttendeesSetOut(version=event.version)


@invitations.post("/response", response_model=AttendeeOut)
async def respond(
    event_id: uuid.UUID, body: ResponseIn, actor: ActorDep, session: SessionDep
) -> AttendeeOut:
    """One's answer to the event (403 `event.not_invited` without an invitation), at
    the event's version read (409 after a change)."""
    answered = await InvitationService(session).respond(
        actor, event_id, body.response, version=body.version
    )
    return AttendeeOut.listed(answered)
