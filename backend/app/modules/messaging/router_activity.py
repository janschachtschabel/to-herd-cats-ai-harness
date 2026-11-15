"""Routes of the activity view ("Für mich", spec 6.2): the caller's own
notifications only."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.messaging.activity import ActivityService
from app.modules.messaging.activity_schemas import ActivityCountOut, ActivityOut

activity = APIRouter(prefix="/activity", tags=["messaging"])


@activity.get("", response_model=Page[ActivityOut])
async def list_activity(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    include_done: Annotated[bool, Query(description="true: done entries too")] = False,
) -> Page[ActivityOut]:
    """The caller's notifications, newest first."""
    page = await ActivityService(session).list(actor, params, only_open=not include_done)
    return Page[ActivityOut](
        items=[ActivityOut.of(e) for e in page.items], next_cursor=page.next_cursor
    )


@activity.get("/count", response_model=ActivityCountOut)
async def count_activity(actor: ActorDep, session: SessionDep) -> ActivityCountOut:
    count = await ActivityService(session).count_open(actor)
    return ActivityCountOut(open=count.open, unread=count.unread)


@activity.post("/read-all", status_code=204)
async def read_all(actor: ActorDep, session: SessionDep) -> None:
    await ActivityService(session).read_all(actor)


@activity.post("/{notification_id}/read", status_code=204)
async def mark_read(notification_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await ActivityService(session).mark_read(actor, notification_id)


@activity.post("/{notification_id}/done", status_code=204)
async def mark_done(notification_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await ActivityService(session).mark_done(actor, notification_id)
