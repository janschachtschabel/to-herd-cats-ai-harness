"""Import and export routes. An import is the ZIP as the raw request body; its body
limit is `HERD_IMPORT_MAX_BYTES` (`web/public.body_limits`)."""

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.core.downloads import content_disposition, file_chunks
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.auth.write_limits import UPLOAD
from app.modules.wiki.export import PageExport
from app.modules.wiki.transfer import ImportResult, PageImport

space_transfer = APIRouter(prefix="/spaces/{space_id}", tags=["wiki"])
page_export = APIRouter(prefix="/pages/{page_id}", tags=["wiki"])

_ZIP_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
    }
}
_DOWNLOAD = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-cache"}


class SkippedOut(BaseModel):
    """`path`: the entry's name in the archive. `reason`: unsafe_path, not_markdown,
    exists, duplicate, too_deep, too_large, invalid_text, unreadable, no_page, or why an
    attachment was refused (type_not_allowed, type_mismatch, filename_invalid)."""

    path: str
    reason: str


class ImportResultOut(BaseModel):
    """`created`: pages, folders without a file of their own included."""

    created: int
    attachments: int
    skipped: list[SkippedOut]

    @classmethod
    def of(cls, result: ImportResult) -> "ImportResultOut":
        return cls(
            created=result.created,
            attachments=result.attachments,
            skipped=[SkippedOut(path=s.path, reason=s.reason) for s in result.skipped],
        )


@space_transfer.post(
    "/import", response_model=ImportResultOut, openapi_extra=_ZIP_BODY, dependencies=UPLOAD
)
async def import_space(
    space_id: uuid.UUID, request: Request, actor: ActorDep, session: SessionDep
) -> ImportResultOut:
    """Pages from a Markdown ZIP (`space.manage`); 413 `import.too_large` over 2,000
    entries or 200 MB unpacked, 422 `import.invalid_zip` for anything else."""
    result = await PageImport(session).import_zip(actor, space_id, request.stream())
    return ImportResultOut.of(result)


@space_transfer.get(
    "/export",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/zip": {}}}},
)
async def export_space(
    space_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> StreamingResponse:
    """The pages the caller may read (drafts with `page.edit`) and their attachments."""
    export = await PageExport(session).export_space(actor, space_id)
    headers = {
        **_DOWNLOAD,
        "Content-Length": str(export.size),
        "Content-Disposition": content_disposition("attachment", export.filename),
    }
    return StreamingResponse(
        file_chunks(export.file), media_type="application/zip", headers=headers
    )


@page_export.get(
    "/export",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}}}},
)
async def export_page(page_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> Response:
    filename, text = await PageExport(session).export_page(actor, page_id)
    headers = {**_DOWNLOAD, "Content-Disposition": content_disposition("attachment", filename)}
    return Response(text, media_type="text/markdown; charset=utf-8", headers=headers)
