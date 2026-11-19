import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.calendars.schemas import (
    CalendarCreate,
    CalendarOut,
    CalendarSettingsIn,
    CalendarSettingsOut,
    CalendarUpdate,
)
from app.modules.calendars.service import CalendarService, NewCalendar
from app.modules.calendars.settings import CalendarSettingsService

calendars = APIRouter(prefix="/calendars", tags=["calendars"])
space_calendars = APIRouter(prefix="/spaces/{space_id}/calendars", tags=["calendars"])
calendar_settings = APIRouter(prefix="/admin/calendar-settings", tags=["calendars"])


@calendars.get("", response_model=Page[CalendarOut])
async def list_calendars(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[CalendarOut]:
    """The calendars of the spaces one belongs to (or open spaces one reads), the same
    for admins; another space's calendars only by naming it."""
    page = await CalendarService(session).list(actor, params)
    return Page[CalendarOut](
        items=[CalendarOut.of(c) for c in page.items], next_cursor=page.next_cursor
    )


@space_calendars.get("", response_model=Page[CalendarOut])
async def list_space_calendars(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[CalendarOut]:
    page = await CalendarService(session).list_in(actor, space_id, params)
    return Page[CalendarOut](
        items=[CalendarOut.of(c) for c in page.items], next_cursor=page.next_cursor
    )


@space_calendars.post("", response_model=CalendarOut, status_code=201)
async def create_calendar(
    space_id: uuid.UUID, body: CalendarCreate, actor: ActorDep, session: SessionDep
) -> CalendarOut:
    new = NewCalendar(name=body.name, color=body.color, time_zone=body.time_zone)
    return CalendarOut.of(await CalendarService(session).create(actor, space_id, new))


@calendars.patch("/{calendar_id}", response_model=CalendarOut)
async def update_calendar(
    calendar_id: uuid.UUID, body: CalendarUpdate, actor: ActorDep, session: SessionDep
) -> CalendarOut:
    values = {name: getattr(body, name) for name in body.model_fields_set if name != "version"}
    calendar = await CalendarService(session).update(actor, calendar_id, body.version, values)
    return CalendarOut.of(calendar)


@calendars.delete("/{calendar_id}", status_code=204)
async def archive_calendar(
    calendar_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Response:
    """Archives the calendar: out of every list, 404 by id."""
    await CalendarService(session).archive(actor, calendar_id, version)
    return Response(status_code=204)


@calendar_settings.get("", response_model=CalendarSettingsOut)
async def get_calendar_settings(actor: ActorDep, session: SessionDep) -> CalendarSettingsOut:
    return CalendarSettingsOut.of(await CalendarSettingsService(session).get(actor))


@calendar_settings.put("", response_model=CalendarSettingsOut)
async def set_calendar_settings(
    body: CalendarSettingsIn, actor: ActorDep, session: SessionDep
) -> CalendarSettingsOut:
    found = await CalendarSettingsService(session).set(actor, body.sync_enabled, body.version)
    return CalendarSettingsOut.of(found)
