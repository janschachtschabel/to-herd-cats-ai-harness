from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.errors import ValidationFailed
from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.calendars.overlay_schemas import OverlayOut
from app.modules.calendars.overlays import OverlayKind, list_overlays

overlays = APIRouter(prefix="/calendar/overlays", tags=["calendars"])

KINDS_MAX = 64


@overlays.get("", response_model=Page[OverlayOut])
async def list_calendar_overlays(
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to", description="the first day after the range")],
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    kinds: Annotated[
        str | None,
        Query(
            max_length=KINDS_MAX,
            description="comma-separated: tickets, sprints, automations (default: all)",
        ),
    ] = None,
    time_zone: Annotated[
        str | None,
        Query(max_length=64, description="the viewer's zone (an automation's day), default UTC"),
    ] = None,
) -> Page[OverlayOut]:
    """Ticket due dates, sprints and automations' next terms in the days `[from, to)`,
    stored nowhere: of the spaces one belongs to (never by admin power), automations
    as their sight rule shows them. By (starts_on, kind, id); a cursor holds
    `time_zone` and is valid with it only (422 `calendar.cursor_time_zone`)."""
    page = await list_overlays(
        session,
        actor,
        start=start,
        end=end,
        kinds=_kinds(kinds),
        params=params,
        viewer_zone=time_zone,
    )
    return Page[OverlayOut](
        items=[OverlayOut.of(o) for o in page.items], next_cursor=page.next_cursor
    )


def _kinds(text: str | None) -> set[OverlayKind]:
    if text is None:
        return set(OverlayKind)
    try:
        return {OverlayKind(part.strip()) for part in text.split(",")}
    except ValueError:
        raise ValidationFailed(code="calendar.overlay_kind_unknown") from None
