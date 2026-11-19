"""Attachment routes. Uploads are the raw file as the request body (any content type;
the type is decided by the content), the name in `?filename=`; their body limit is
`HERD_ATTACHMENT_MAX_BYTES` (`web/public.body_limits`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.core.downloads import content_disposition
from app.core.pagination import Page, PageParams
from app.core.security_headers import API_POLICY
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.auth.write_limits import UPLOAD
from app.modules.wiki import filetypes
from app.modules.wiki.ai_lock import AiLockService
from app.modules.wiki.attachment_schemas import AttachmentOut
from app.modules.wiki.attachments import AttachmentService
from app.modules.wiki.models import Attachment
from app.modules.wiki.schemas import AiLockIn

page_attachments = APIRouter(prefix="/pages/{page_id}/attachments", tags=["wiki"])
attachments = APIRouter(prefix="/attachments", tags=["wiki"])

_INLINE_MIMES = {t.mime for t in (filetypes.PNG, filetypes.JPEG, filetypes.GIF, filetypes.WEBP)}
_TEXT_MIMES = {t.mime for t in filetypes.TEXT_TYPES}
_UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}


def download_headers(attachment: Attachment, inline: bool) -> dict[str, str]:
    shown = inline and attachment.mime in _INLINE_MIMES
    return {
        "Content-Length": str(attachment.size),
        "Content-Disposition": content_disposition(
            "inline" if shown else "attachment", attachment.filename
        ),
        "X-Content-Type-Options": "nosniff",
        # Opened directly, nothing in it runs or loads anything.
        "Content-Security-Policy": f"{API_POLICY}; sandbox",
        "Cache-Control": "private, no-cache",
    }


@page_attachments.post(
    "",
    response_model=AttachmentOut,
    status_code=201,
    openapi_extra=_UPLOAD_BODY,
    dependencies=UPLOAD,
)
async def upload_attachment(
    page_id: uuid.UUID,
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=1000)],
    actor: ActorDep,
    session: SessionDep,
) -> AttachmentOut:
    """Upload a file (`page.edit`): PNG, JPEG, GIF, WebP, PDF, TXT, Markdown, CSV, JSON,
    DOCX, XLSX, PPTX or ZIP, decided by the content; 415 otherwise or when the name's
    extension does not fit it; 413 over the size limit."""
    attachment = await AttachmentService(session).upload(actor, page_id, filename, request.stream())
    return AttachmentOut.of(attachment)


@page_attachments.get("", response_model=Page[AttachmentOut])
async def list_attachments(
    page_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[AttachmentOut]:
    page = await AttachmentService(session).list(actor, page_id, params)
    return Page[AttachmentOut](
        items=[AttachmentOut.of(a) for a in page.items], next_cursor=page.next_cursor
    )


@attachments.get(
    "/{attachment_id}",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_attachment(
    attachment_id: uuid.UUID,
    actor: ActorDep,
    session: SessionDep,
    inline: Annotated[bool, Query(description="show a raster image in the page")] = False,
) -> StreamingResponse:
    attachment, chunks = await AttachmentService(session).open(actor, attachment_id)
    media_type = attachment.mime
    if media_type in _TEXT_MIMES:
        media_type += "; charset=utf-8"
    return StreamingResponse(
        chunks, media_type=media_type, headers=download_headers(attachment, inline)
    )


@attachments.delete("/{attachment_id}", status_code=204)
async def delete_attachment(attachment_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    """`page.edit` on its page; the file goes when no other attachment uses it."""
    await AttachmentService(session).delete(actor, attachment_id)


@attachments.put("/{attachment_id}/ai-lock", response_model=AttachmentOut)
async def set_attachment_ai_lock(
    attachment_id: uuid.UUID, body: AiLockIn, actor: ActorDep, session: SessionDep
) -> AttachmentOut:
    """`page.moderate` in its page's space; the attachment's `version` (stale → 409)."""
    attachment = await AiLockService(session).set_attachment(
        actor, attachment_id, body.no_ai, body.version
    )
    return AttachmentOut.of(attachment)
