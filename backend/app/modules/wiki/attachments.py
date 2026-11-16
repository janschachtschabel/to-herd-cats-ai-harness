"""Attachments (spec 9): files on a page, read by whoever may read the page, uploaded
and deleted with `page.edit` on it. Attachments of a page in the trash are out of
reach until it is restored; purging a page deletes them.

An upload is read once into a spool (`core/uploads.py`), up to
`HERD_ATTACHMENT_MAX_BYTES` (413 above), and its type decided by the content
(`filetypes.py`, 415). The bytes are stored once per organisation and content, under
a key built from the organisation and the SHA-256 (never from the file name); a file
leaves the storage with the last attachment that uses it. Writing, counting and
deleting one content's file are serialised (`lock_blob`), so an upload and a delete
of the same content cannot lose the file. A deleted attachment's file stays for a
grace period (a tombstone, `core/storage_tombstones.py`, plan M9 decision 4) and is
removed by the worker's due loop if no attachment uses it by then.
"""

import asyncio
import builtins
import unicodedata
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor
from app.core.config import get_settings
from app.core.errors import NotFound, ValidationFailed
from app.core.outbox import emit
from app.core.pagination import PageParams, decode_id_cursor, id_page
from app.core.storage import Storage, StoredFileMissing, get_storage
from app.core.storage_tombstones import bury
from app.core.uploads import spool
from app.modules.audit.recorder import record
from app.modules.wiki import filetypes
from app.modules.wiki.attachments_repository import AttachmentRepository
from app.modules.wiki.events import ATTACHMENT_UPLOADED
from app.modules.wiki.models import MAX_FILENAME_CHARS, Attachment, Page
from app.modules.wiki.visibility import PageReader


def attachment_not_found() -> NotFound:
    return NotFound(code="attachment.not_found")


def clean_filename(raw: str) -> str:
    """The name to keep: NFC, control characters as spaces, path separators as `_`,
    trimmed; 422 if nothing is left or it is too long."""
    name = unicodedata.normalize("NFC", raw)
    name = "".join(" " if unicodedata.category(c) in ("Cc", "Zl", "Zp") else c for c in name)
    name = name.replace("/", "_").replace("\\", "_").strip()
    if not name or len(name) > MAX_FILENAME_CHARS:
        raise ValidationFailed(code="attachment.filename_invalid")
    return name


def storage_key(org_id: uuid.UUID, sha256: str) -> str:
    return f"attachments/{org_id}/{sha256}"


class AttachmentService:
    def __init__(self, session: AsyncSession, storage: Storage | None = None) -> None:
        self.session = session
        self.reader = PageReader(session)
        self.storage = storage or get_storage()

    def repo(self, actor: Actor) -> AttachmentRepository:
        return AttachmentRepository(self.session, self.reader.scope(actor))

    async def upload(
        self, actor: Actor, page_id: uuid.UUID, filename: str, stream: AsyncIterator[bytes]
    ) -> Attachment:
        """The upload route's: rights first, so nothing is read from someone who may
        not upload. The request's body is then read with no transaction open (no
        pooled connection held, however slowly it arrives), see `add`. Emits
        `attachment.uploaded` (ids only; an import's attachments emit nothing)."""
        await self._editable(actor, page_id)
        await self.session.commit()
        attachment = await self.add(actor, page_id, filename, stream)
        await emit(
            self.session,
            type=ATTACHMENT_UPLOADED,
            actor=actor,
            space_id=attachment.space_id,
            subject_type="attachment",
            subject_id=attachment.id,
            payload={"attachment_id": str(attachment.id), "page_id": str(attachment.page_id)},
        )
        return attachment

    async def add(
        self, actor: Actor, page_id: uuid.UUID, filename: str, stream: AsyncIterator[bytes]
    ) -> Attachment:
        """Read `stream`, check the rights (again), store the file, within the caller's
        transaction (an import's entries stay part of the import's one transaction)."""
        name = clean_filename(filename)
        limit = get_settings().attachment_max_bytes
        with await spool(stream, limit, code="attachment.too_large") as body:
            page = await self._editable(actor, page_id)
            kind = await asyncio.to_thread(filetypes.detect, body.head, body.text, body.file, name)
            attachments = self.repo(actor)
            await attachments.lock_blob(body.sha256)
            key = storage_key(actor.org_id, body.sha256)
            await self.storage.put(key, body.chunks(), size=body.size, sha256=body.sha256)
            attachment = await attachments.add(
                Attachment(
                    org_id=actor.org_id,
                    space_id=page.space_id,
                    page_id=page.id,
                    filename=name,
                    mime=kind.mime,
                    size=body.size,
                    sha256=body.sha256,
                    storage_key=key,
                    uploaded_by_type=actor.principal.type,
                    uploaded_by_id=actor.principal.id,
                )
            )
        details = {"page_id": str(page.id), "filename": name, "size": attachment.size}
        await record(
            self.session, actor, "attachment.uploaded", "attachment", attachment.id, details
        )
        return attachment

    async def _editable(self, actor: Actor, page_id: uuid.UUID) -> Page:
        page = await self.reader.readable(actor, page_id)
        await self.reader.require_in_space(actor, Action.PAGE_EDIT, page)
        return page

    async def list(
        self, actor: Actor, page_id: uuid.UUID, params: PageParams
    ) -> pagination.Page[Attachment]:
        page = await self.reader.readable(actor, page_id)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).page(page.id, after, params.limit + 1)
        return id_page(rows, params.limit, lambda a: a.id)

    async def open(
        self, actor: Actor, attachment_id: uuid.UUID
    ) -> tuple[Attachment, AsyncIterator[bytes]]:
        attachment, _ = await self._reachable(actor, attachment_id)
        try:
            return attachment, await self.storage.open(attachment.storage_key)
        except StoredFileMissing:
            raise attachment_not_found() from None

    async def delete(self, actor: Actor, attachment_id: uuid.UUID) -> None:
        attachment, page = await self._reachable(actor, attachment_id)
        await self.reader.require_in_space(actor, Action.PAGE_EDIT, page)
        attachments = self.repo(actor)
        await attachments.delete(attachment)
        await self._drop_unused(actor, [attachment])
        details = {"page_id": str(page.id), "filename": attachment.filename}
        await record(
            self.session, actor, "attachment.deleted", "attachment", attachment.id, details
        )

    async def purge_pages(self, actor: Actor, page_ids: builtins.list[uuid.UUID]) -> None:
        """For pages about to be deleted for good: their attachments and the files no
        other attachment uses. The caller has checked the right to purge."""
        gone = await self.repo(actor).delete_of_pages(page_ids)
        await self._drop_unused(actor, gone)

    async def _drop_unused(self, actor: Actor, gone: builtins.list[Attachment]) -> None:
        """The files of deleted rows get a tombstone in this transaction; the due loop
        removes each after the grace period if no attachment uses it then
        (`core/storage_tombstones.py`, `attachment_files.blob_in_use`), so a backup's
        snapshot finds every file of its rows."""
        await bury(self.session, actor.org_id, (storage_key(actor.org_id, a.sha256) for a in gone))

    async def _audit(
        self, actor: Actor, action: str, attachment: Attachment, details: dict[str, Any]
    ) -> None:
        await record(self.session, actor, action, "attachment", attachment.id, details)

    async def _reachable(self, actor: Actor, attachment_id: uuid.UUID) -> tuple[Attachment, Page]:
        """The attachment and its page if the actor may read the page; otherwise the
        same 404 as for an unknown id."""
        attachment = await self.repo(actor).get(attachment_id)
        if attachment is None:
            raise attachment_not_found()
        try:
            page = await self.reader.readable(actor, attachment.page_id)
        except NotFound:
            raise attachment_not_found() from None
        return attachment, page
