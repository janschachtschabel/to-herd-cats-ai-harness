"""Backups in the administration (plan M9 task 13): `/api/backups/...`, only for
`backup.manage` (owners); anyone else gets 404 `backup.not_found` on every route. An
upload is the archive as the raw request body (`application/x-tar`), its body limit
HERD_BACKUP_UPLOAD_MAX_BYTES (`web/public.body_limits`)."""

from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import StreamingResponse

from app.core.downloads import content_disposition, file_chunks
from app.core.errors import NotFound
from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep, SettingsDep
from app.modules.backups.schemas import (
    ArchiveCheckOut,
    ArchiveOut,
    BackupRunOut,
    ReplaceIn,
    ReplaceOut,
    RestoreStatusOut,
)
from app.modules.backups.service import BackupAdmin

router = APIRouter(prefix="/backups", tags=["backups"])

PageQuery = Annotated[PageParams, Query()]
_TAR_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/x-tar": {"schema": {"type": "string", "format": "binary"}}},
    }
}
_DOWNLOAD = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"}


@router.get("", response_model=Page[BackupRunOut])
async def list_backups(
    page: PageQuery, actor: ActorDep, session: SessionDep, settings: SettingsDep
) -> Page[BackupRunOut]:
    """The backups, newest first."""
    runs = await BackupAdmin(session, settings).runs(actor, page.limit, page.cursor)
    return Page[BackupRunOut](
        items=[BackupRunOut.of(r) for r in runs.items], next_cursor=runs.next_cursor
    )


@router.post("", response_model=BackupRunOut, status_code=status.HTTP_202_ACCEPTED)
async def start_backup(actor: ActorDep, session: SessionDep, settings: SettingsDep) -> BackupRunOut:
    """Back up now: a worker makes the backup; `backup.changed` tells its progress.
    409 `backup.already_running` while one runs or waits, `backup.busy` while another
    request is being handled."""
    return BackupRunOut.of(await BackupAdmin(session, settings).request(actor))


@router.get("/restore", response_model=RestoreStatusOut)
async def restore_status(
    actor: ActorDep, session: SessionDep, settings: SettingsDep
) -> RestoreStatusOut:
    """The last attempt to replace the installation from the administration."""
    return RestoreStatusOut(attempt=await BackupAdmin(session, settings).last_restore(actor))


@router.get("/archives", response_model=Page[ArchiveOut])
async def list_archives(
    page: PageQuery, actor: ActorDep, session: SessionDep, settings: SettingsDep
) -> Page[ArchiveOut]:
    """The archives in the backups directory, newest first."""
    found = await BackupAdmin(session, settings).archives(actor, page.limit, page.cursor)
    return Page[ArchiveOut](
        items=[ArchiveOut.of(a) for a in found.items], next_cursor=found.next_cursor
    )


@router.post(
    "/archives",
    response_model=ArchiveOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra=_TAR_BODY,
)
async def upload_archive(
    request: Request, actor: ActorDep, session: SessionDep, settings: SettingsDep
) -> ArchiveOut:
    """An archive from elsewhere, checked: 413 `backup.upload_too_large`, 422
    `backup.archive_invalid` with the problems."""
    archive = await BackupAdmin(session, settings).upload(actor, request.stream())
    return ArchiveOut.of(archive)


@router.get(
    "/archives/{name}",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/x-tar": {}}}},
)
async def download_archive(
    name: str, actor: ActorDep, session: SessionDep, settings: SettingsDep
) -> StreamingResponse:
    archive = await BackupAdmin(session, settings).download(actor, name)
    try:
        handle = archive.path.open("rb")
    except OSError:  # removed meanwhile (retention): the audit entry rolls back
        raise NotFound(code="backup.not_found") from None
    headers = {
        **_DOWNLOAD,
        "Content-Length": str(archive.size),
        "Content-Disposition": content_disposition("attachment", archive.name),
    }
    return StreamingResponse(file_chunks(handle), media_type="application/x-tar", headers=headers)


@router.post("/archives/{name}/check", response_model=ArchiveCheckOut)
async def check_archive(
    name: str, actor: ActorDep, session: SessionDep, settings: SettingsDep
) -> ArchiveCheckOut:
    """The archive against this installation; `can_replace` when nothing blocks."""
    report = await BackupAdmin(session, settings).check(actor, name)
    return ArchiveCheckOut.of(name, report)


@router.post(
    "/archives/{name}/replace", response_model=ReplaceOut, status_code=status.HTTP_202_ACCEPTED
)
async def replace_installation(
    name: str, body: ReplaceIn, actor: ActorDep, session: SessionDep, settings: SettingsDep
) -> ReplaceOut:
    """Replace the whole installation with the archive (a safety archive first, then
    maintenance, then everyone signed out). 422 `backup.confirm_mismatch`, 409
    `backup.already_running`, `backup.busy`, `backup.restore_running`,
    `backup.replace_refused`."""
    archive = await BackupAdmin(session, settings).replace(actor, name, body.confirm)
    return ReplaceOut(archive_name=archive.name)
