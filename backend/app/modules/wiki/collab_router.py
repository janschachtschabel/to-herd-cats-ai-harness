"""The internal collab API on the internal port (`/internal/collab/*`, behind the
internal token, see `web/internal.py`). Only the collab process calls it."""

import base64
import binascii
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.core.errors import ValidationFailed
from app.modules.auth.deps import SessionDep
from app.modules.wiki.collab_schemas import (
    AuthIn,
    AuthOut,
    CheckIn,
    CheckOut,
    CollabUserOut,
    LiveDocumentOut,
    SaveIn,
    SaveOut,
)
from app.modules.wiki.collab_service import CollabService

router = APIRouter(prefix="/collab", tags=["internal"])


@router.post("/auth", response_model=AuthOut)
async def authenticate(body: AuthIn, session: SessionDep) -> AuthOut:
    grant = await CollabService(session).authenticate(body.session_token, body.page_id)
    return AuthOut(
        user=CollabUserOut(id=grant.user.id, name=grant.user.name),
        session_id=grant.session_id,
        generation=grant.generation,
        can_edit=True,
    )


@router.get("/pages/{page_id}", response_model=LiveDocumentOut)
async def load(
    page_id: uuid.UUID,
    session_id: uuid.UUID,
    session: SessionDep,
    generation: Annotated[int | None, Query(ge=0)] = None,
) -> LiveDocumentOut:
    doc = await CollabService(session).load(page_id, session_id, generation)
    ydoc_b64 = base64.b64encode(doc.ydoc).decode("ascii") if doc.ydoc is not None else None
    return LiveDocumentOut(
        generation=doc.generation, ydoc_b64=ydoc_b64, content_md=doc.content_md, title=doc.title
    )


@router.put("/pages/{page_id}", response_model=SaveOut)
async def save(page_id: uuid.UUID, body: SaveIn, session: SessionDep) -> SaveOut:
    try:
        ydoc = base64.b64decode(body.ydoc_b64, validate=True)
    except binascii.Error:
        raise ValidationFailed(code="collab.state_invalid") from None
    page = await CollabService(session).save(
        page_id,
        generation=body.generation,
        ydoc=ydoc,
        content_md=body.content_md,
        session_ids=body.editor_session_ids,
        session_key=body.session_key,
    )
    return SaveOut(generation=page.collab_generation, version=page.version)


@router.post("/pages/{page_id}/check", response_model=CheckOut)
async def check(page_id: uuid.UUID, body: CheckIn, session: SessionDep) -> CheckOut:
    result = await CollabService(session).check(
        page_id, body.session_ids, body.generation, unsaved=body.unsaved_session_ids
    )
    return CheckOut(
        generation_ok=result.generation_ok,
        generation=result.generation,
        revoked_session_ids=result.revoked.session_ids,
        revoked_user_ids=result.revoked.user_ids,
        ended_session_ids=result.ended_session_ids,
    )


@router.post("/pages/{page_id}/unrepresentable", status_code=204)
async def unrepresentable(page_id: uuid.UUID) -> Response:
    """The collab process stored nothing for the latest state of the page: it cannot be
    written as Markdown that reads back as what the editors see (counted only)."""
    CollabService.unrepresentable()
    return Response(status_code=204)
