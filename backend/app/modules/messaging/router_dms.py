"""Routes of direct messages and of the admin's inspection of them. A DM's messages go
through the conversation routes (`router.py`); an inspection reads only through its
own route here."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.messaging.dm_schemas import (
    DmOpen,
    DmOut,
    InspectableDmOut,
    InspectionCreate,
    InspectionOut,
)
from app.modules.messaging.dms import DmService
from app.modules.messaging.inspect import InspectService, withheld
from app.modules.messaging.message_schemas import MessageOut
from app.modules.messaging.router import message_page
from app.modules.messaging.schemas import ConversationOut

dms = APIRouter(prefix="/dms", tags=["messaging"])
dm_inspect = APIRouter(prefix="/admin/dm-inspect", tags=["messaging"])


@dms.post(
    "",
    response_model=ConversationOut,
    status_code=201,
    responses={200: {"model": ConversationOut, "description": "the group's conversation"}},
)
async def open_dm(
    body: DmOpen, response: Response, actor: ActorDep, session: SessionDep
) -> ConversationOut:
    """The caller's conversation with these people, or with an agent (`ai.use`): new
    (201) or the one they have."""
    opened = await DmService(session).open(actor, body.user_ids, body.agent_id)
    if not opened.created:
        response.status_code = 200
    return ConversationOut.of(opened.conversation, can_post=True, participants=opened.participants)


@dms.get("", response_model=Page[DmOut])
async def list_dms(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[DmOut]:
    """The caller's direct messages, the most recently active first."""
    page = await DmService(session).list(actor, params)
    return Page[DmOut](items=[DmOut.of_entry(e) for e in page.items], next_cursor=page.next_cursor)


@dm_inspect.get("", response_model=Page[InspectableDmOut])
async def find_dms(
    user_id: Annotated[uuid.UUID, Query(description="whose direct messages")],
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[InspectableDmOut]:
    """`dm.inspect`: a person's DMs, participants and times only (audited)."""
    page = await InspectService(session).find(actor, user_id, params)
    return Page[InspectableDmOut](
        items=[InspectableDmOut.of(e) for e in page.items], next_cursor=page.next_cursor
    )


@dm_inspect.post("", response_model=InspectionOut, status_code=201)
async def grant_inspection(
    body: InspectionCreate, actor: ActorDep, session: SessionDep
) -> InspectionOut:
    """`dm.inspect`: read one DM for 60 minutes, with a reason (audited, and shown to
    its participants)."""
    inspection = await InspectService(session).grant(actor, body.conversation_id, body.reason)
    return InspectionOut.of(inspection)


@dm_inspect.get("/{inspection_id}/messages", response_model=Page[MessageOut])
async def inspected_messages(
    inspection_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[MessageOut]:
    """The inspected DM's messages, replies included, newest first; 404 once the
    inspection has expired."""
    page = await InspectService(session).messages(actor, inspection_id, params)
    return withheld(await message_page(session, actor, page))
