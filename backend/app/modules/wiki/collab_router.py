"""The internal collab API on the internal port (`/internal/collab/*`, behind the
internal token, see `web/internal.py`). Only the collab process calls it, and only
with the grants the relay handed it (plan M9 decision 16): a load names its grant in
the header `X-Herd-Grant` (never in the URL)."""

import base64
import binascii
import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response

from app.core.errors import ValidationFailed
from app.modules.auth.deps import SessionDep
from app.modules.wiki.collab_grants import MAX_GRANT_CHARS
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
    joined = await CollabService(session).join(body.grant, body.page_id, body.generation)
    return AuthOut(
        user=CollabUserOut(id=joined.user.id, name=joined.user.name),
        session_ref=joined.session_ref,
        generation=joined.generation,
        can_edit=True,
    )


@router.get("/pages/{page_id}", response_model=LiveDocumentOut)
async def load(
    page_id: uuid.UUID,
    session: SessionDep,
    generation: Annotated[int, Query(ge=0)],
    grant: Annotated[str, Header(alias="X-Herd-Grant", max_length=MAX_GRANT_CHARS)],
) -> LiveDocumentOut:
    doc = await CollabService(session).load(page_id, grant, generation)
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
        grants=body.editor_grants,
        session_key=body.session_key,
    )
    return SaveOut(generation=page.collab_generation, version=page.version)


@router.post("/pages/{page_id}/check", response_model=CheckOut)
async def check(page_id: uuid.UUID, body: CheckIn, session: SessionDep) -> CheckOut:
    result = await CollabService(session).check(
        page_id, body.grants, body.generation, unsaved=body.unsaved_grants
    )
    return CheckOut(
        generation_ok=result.generation_ok,
        generation=result.generation,
        revoked_grants=result.revoked_grants,
        ended_grants=result.ended_grants,
    )


@router.post("/pages/{page_id}/unrepresentable", status_code=204)
async def unrepresentable(page_id: uuid.UUID) -> Response:
    """The collab process stored nothing for the latest state of the page: it cannot be
    written as Markdown that reads back as what the editors see (counted only)."""
    CollabService.unrepresentable()
    return Response(status_code=204)


@router.post("/pages/{page_id}/load-mutation", status_code=204)
async def load_mutation(page_id: uuid.UUID) -> Response:
    """A browser's live editor changed the document it had just loaded before anyone
    typed; it stopped instead of sending the change (counted only)."""
    CollabService.load_mutation()
    return Response(status_code=204)
