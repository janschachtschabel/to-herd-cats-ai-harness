import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import AwareDatetime

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.calendars.event_schemas import (
    EventChangeOut,
    EventCreate,
    EventOut,
    EventUpdate,
    OccurrenceOut,
)
from app.modules.calendars.event_writes import Scope
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
    time_zone: Annotated[
        str | None,
        Query(max_length=64, description="the viewer's zone (all-day days), default UTC"),
    ] = None,
    mine: Annotated[
        bool, Query(description="my events: only those I organise or am invited to")
    ] = False,
) -> Page[OccurrenceOut]:
    """Every occurrence overlapping `[from, to)` of the events one may list (member
    spaces and the events one organises or is invited to; another space's only by
    naming it with `space_id`; `mine`: only one's own and those one is invited to), by
    start. Private events of others come `redacted`; `q` searches titles one sees. A
    cursor holds `time_zone` and is valid with it only (422 `calendar.cursor_time_zone`)."""
    return await list_window(
        session,
        actor,
        start=start,
        end=end,
        calendar_ids=calendar_ids,
        space_id=space_id,
        mine=mine,
        query=q,
        params=params,
        viewer_zone=time_zone,
    )


@events.get("/{event_id}", response_model=EventOut)
async def get_event(event_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> EventOut:
    seen = await EventService(session).get(actor, event_id)
    return EventOut.of(seen.event, seen.sight)


Occurrence = Annotated[
    str | None,
    Query(
        max_length=32,
        description="with scope this or following: the occurrence's recurrence_id "
        "(its wall time, as the window names it)",
    ),
]


@events.patch("/{event_id}", response_model=EventChangeOut)
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    actor: ActorDep,
    session: SessionDep,
    scope: Scope = Scope.ALL,
    occurrence: Occurrence = None,
    dry_run: Annotated[bool, Query(description="only count what the change drops")] = False,
) -> EventChangeOut:
    """Changes the event (`calendar.write` and full sight; 403 `event.private` with
    "busy" sight), at the version read (409 `event.version_conflict`): the whole series
    (`scope=all`), one occurrence (`this`: an override) or this and the following
    (`following`: the series is split)."""
    changed = await EventService(session).update(
        actor,
        event_id,
        body.change(),
        scope=scope,
        occurrence=occurrence,
        version=body.version,
        dry_run=dry_run,
    )
    return EventChangeOut(
        event=EventOut.of(changed.event, changed.sight),
        dropped_overrides=changed.dropped_overrides,
        dropped_exdates=changed.dropped_exdates,
    )


@events.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
    scope: Scope = Scope.ALL,
    occurrence: Occurrence = None,
) -> Response:
    """Deletes the event (a tombstone for 30 days): the series with its overrides, one
    occurrence (`this`), or this and the following (`following`)."""
    await EventService(session).delete(
        actor, event_id, scope=scope, occurrence=occurrence, version=version
    )
    return Response(status_code=204)
