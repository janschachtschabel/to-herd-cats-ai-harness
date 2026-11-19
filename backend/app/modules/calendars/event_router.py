import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.calendars.event_schemas import EventCreate, EventOut, OccurrenceOut
from app.modules.calendars.events import EventService
from app.modules.calendars.sight import Sight
from app.modules.calendars.window import list_window

calendar_events = APIRouter(prefix="/calendars/{calendar_id}/events", tags=["calendar events"])
window = APIRouter(prefix="/calendar/events", tags=["calendar events"])
events = APIRouter(prefix="/events", tags=["calendar events"])

MAX_CALENDAR_IDS = 100
QUERY_MAX = 300


@calendar_events.post("", response_model=EventOut, status_code=201)
async def create_event(
    calendar_id: uuid.UUID, body: EventCreate, actor: ActorDep, session: SessionDep
) -> EventOut:
    """A new event in the calendar (`calendar.write` in its space); the caller is its
    organiser and sees it in full."""
    event = await EventService(session).create(actor, calendar_id, body.new())
    return EventOut.of(event, Sight.FULL)  # the caller organises it


@window.get("", response_model=Page[OccurrenceOut])
async def list_events(
    start: Annotated[AwareDatetime, Query(alias="from")],
    end: Annotated[AwareDatetime, Query(alias="to")],
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    calendar_ids: Annotated[list[uuid.UUID] | None, Query(max_length=MAX_CALENDAR_IDS)] = None,
    space_id: Annotated[
        uuid.UUID | None, Query(description="the named way: this space's events only")
    ] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=QUERY_MAX)] = None,
    tz: Annotated[
        str | None, Query(max_length=64, description="the viewer's zone (all-day days)")
    ] = None,
) -> Page[OccurrenceOut]:
    """Every occurrence overlapping `[from, to)` of the events one may list (member
    spaces and one's own; another space's only by naming it with `space_id`), by
    start. Private events of others come `redacted`; `q` searches titles one sees."""
    return await list_window(
        session,
        actor,
        start=start,
        end=end,
        calendar_ids=calendar_ids,
        space_id=space_id,
        mine=False,
        query=q,
        params=params,
        viewer_zone=tz,
    )


@events.get("/{event_id}", response_model=EventOut)
async def get_event(event_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> EventOut:
    seen = await EventService(session).get(actor, event_id)
    return EventOut.of(seen.event, seen.sight)
