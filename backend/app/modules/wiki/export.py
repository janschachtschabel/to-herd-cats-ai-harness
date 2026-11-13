"""Exporting a space as a Markdown ZIP, or one page as a `.md` file (spec 9).

The archive has one `<path>.md` per page the actor may read (drafts only with
`page.edit`), with front matter `title`, `status` and `tags` (names), and each page's
attachments under `_attachments/<path>/<file name>`, listed with their ids in
`_attachments/manifest.json` (`attachment_links.py`). `transfer.py` reads it back.
Pages are read in batches of the tree; the archive is written to a temporary file,
not held in memory.
"""

import asyncio
import uuid
import zipfile
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import IO

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.slug import slugify
from app.core.spool import spooled_file
from app.core.storage import Storage, StoredFileMissing, get_storage
from app.modules.spaces.service import SpaceService
from app.modules.tags.models import SubjectType, Tag
from app.modules.tags.repository import tag_repository
from app.modules.wiki import frontmatter
from app.modules.wiki.attachment_links import MANIFEST, manifest_json
from app.modules.wiki.attachments_repository import AttachmentRepository
from app.modules.wiki.import_layout import ATTACHMENTS
from app.modules.wiki.models import Attachment, Page
from app.modules.wiki.visibility import PageReader

BATCH = 100
_SPOOL_BYTES = 1024 * 1024


@dataclass
class Export:
    filename: str
    file: IO[bytes]  # from the start; whoever sends it closes it
    size: int


def page_markdown(page: Page, tags: list[Tag]) -> str:
    meta: frontmatter.Meta = {
        "title": page.title,
        "status": str(page.status),
        "tags": [t.name for t in tags],
    }
    return frontmatter.serialise(meta, page.content_md)


def _archive_name(filename: str, taken: set[str]) -> str:
    """A file name safe inside an archive and unique among `taken`."""
    name = filename if not filename.startswith(".") else f"_{filename}"
    stem, dot, ext = name.rpartition(".")
    stem, ext = (stem, f".{ext}") if dot and stem else (name, "")
    counter, candidate = 2, name
    while candidate in taken:
        candidate, counter = f"{stem} ({counter}){ext}", counter + 1
    taken.add(candidate)
    return candidate


class PageExport:
    def __init__(self, session: AsyncSession, storage: Storage | None = None) -> None:
        self.session = session
        self.reader = PageReader(session)
        self.storage = storage or get_storage()

    async def export_page(self, actor: Actor, page_id: uuid.UUID) -> tuple[str, str]:
        """(file name, Markdown) of a page the actor may read."""
        page = await self.reader.readable(actor, page_id)
        tags = await tag_repository(self.session, actor).tags_for(SubjectType.PAGE, [page.id])
        return f"{page.slug}.md", page_markdown(page, tags.get(page.id, []))

    async def export_space(self, actor: Actor, space_id: uuid.UUID) -> Export:
        space = await SpaceService(self.session).get(actor, space_id)
        drafts = await can(self.session, actor, Action.PAGE_EDIT, space_id)
        file = spooled_file(_SPOOL_BYTES)
        try:
            with zipfile.ZipFile(file, "w", zipfile.ZIP_DEFLATED) as zipped:
                listed: dict[str, uuid.UUID] = {}
                await self._write(actor, space_id, drafts, zipped, listed)
                if listed:
                    zipped.writestr(MANIFEST, manifest_json(listed))
            size = file.tell()
        except BaseException:
            file.close()
            raise
        return Export(f"{slugify(space.name)}.zip", file, size)

    async def _write(
        self,
        actor: Actor,
        space_id: uuid.UUID,
        drafts: bool,
        zipped: zipfile.ZipFile,
        listed: dict[str, uuid.UUID],
    ) -> None:
        pages = self.reader.repo(actor)
        attachments = AttachmentRepository(self.session, self.reader.scope(actor))
        tags = tag_repository(self.session, actor)
        after: tuple[str, uuid.UUID] | None = None
        while batch := await pages.tree_page(space_id, drafts=drafts, after=after, limit=BATCH):
            ids = [p.id for p in batch]
            tagged = await tags.tags_for(SubjectType.PAGE, ids)
            files: dict[uuid.UUID, list[Attachment]] = {}
            for attachment in await attachments.of_pages(ids):
                files.setdefault(attachment.page_id, []).append(attachment)
            for page in batch:
                text = page_markdown(page, tagged.get(page.id, []))
                await asyncio.to_thread(zipped.writestr, f"{page.path}.md", text)
                taken: set[str] = set()
                for attachment in files.get(page.id, []):
                    name = f"{ATTACHMENTS}/{page.path}/{_archive_name(attachment.filename, taken)}"
                    if await self._copy(attachment, name, zipped):
                        listed[name] = attachment.id
            after = (batch[-1].path, batch[-1].id)

    async def _copy(self, attachment: Attachment, name: str, zipped: zipfile.ZipFile) -> bool:
        try:
            chunks = await self.storage.open(attachment.storage_key)
        except StoredFileMissing:
            return False  # gone from the storage: nothing to export
        target = await asyncio.to_thread(zipped.open, name, "w")
        try:
            await _pump(chunks, target)
        finally:
            await asyncio.to_thread(target.close)
        return True


async def _pump(chunks: AsyncIterator[bytes], target: IO[bytes]) -> None:
    async for chunk in chunks:
        await asyncio.to_thread(target.write, chunk)
