"""Importing a Markdown ZIP into a space (spec 9; `space.manage`).

Every `.md` file becomes a page at the path of its folders and name (`a/b.md` and
`a/b/index.md` are both `a/b`), titled by front matter, first heading or file name.
Folders without a file of their own become empty pages. Files under
`_attachments/<page path>/` become attachments of the pages made here. Pages are made
through `PageService` (versions with source `import`), tags and attachments through
their services, so every rule holds: a page is published (front matter `status`,
default `published`) only below a published parent, else it stays a draft. Links to
attachments the archive brought (`_attachments/manifest.json`) are pointed at the new
attachments afterwards, folded into the page's first version (`attachment_links.py`).

What cannot be imported is skipped with a reason; the archive itself is read
defensively (`archive.py`), its layout in `import_layout.py`. The whole import is one
transaction.
"""

import asyncio
import uuid
import zipfile
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.core.access_repository import remembered_facts
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.slug import slugify
from app.core.uploads import spool
from app.modules.audit.recorder import record
from app.modules.tags.models import MAX_TAG_NAME_CHARS
from app.modules.tags.repository import tag_repository
from app.modules.tags.schemas import DEFAULT_COLOR
from app.modules.tags.service import TagService
from app.modules.wiki import archive, frontmatter
from app.modules.wiki.attachment_links import rewrite_links
from app.modules.wiki.attachments import AttachmentService
from app.modules.wiki.import_layout import (
    ATTACHMENTS,
    SLUG_CHARS,
    ArchiveFile,
    layout,
    page_title,
    strings,
    title_of,
)
from app.modules.wiki.models import MAX_CONTENT_CHARS, Page, PageStatus
from app.modules.wiki.models import VersionSource as Source
from app.modules.wiki.service import PageService, Siblings

_SESSION_SECONDS = 24 * 60 * 60  # the import's saves fold into each page's first version


@dataclass(frozen=True, slots=True)
class Skipped:
    path: str  # the entry's name in the archive
    reason: str


@dataclass
class ImportResult:
    created: int = 0
    attachments: int = 0
    skipped: list[Skipped] = field(default_factory=list)


class PageImport:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.pages = PageService(session)
        self.tags = TagService(session)
        self.attachments = AttachmentService(session)

    async def import_zip(
        self, actor: Actor, space_id: uuid.UUID, stream: AsyncIterator[bytes]
    ) -> ImportResult:
        """Rights first: nothing is read from someone who may not import. The body is
        read with no transaction open (no pooled connection held); the rights are
        checked again afterwards."""
        await require(self.session, actor, Action.SPACE_MANAGE, space_id)
        await self.session.commit()
        self.actor, self.space_id = actor, space_id
        self.result = ImportResult()
        self.made: dict[str, Page] = {}
        self.tag_ids: dict[str, uuid.UUID] = {}
        self.session_key = f"import:{uuid.uuid4().hex}"
        self.siblings = Siblings()
        self.new_ids: dict[uuid.UUID, uuid.UUID] = {}  # that attachment → the new one
        limit = get_settings().import_max_bytes
        with await spool(stream, limit, code="import.too_large") as body:
            await require(self.session, actor, Action.SPACE_MANAGE, space_id)
            zipped = await asyncio.to_thread(archive.open_archive, body.file)
            # One operation in one transaction: rights as checked just now, slugs and
            # order per parent read once (thousands of pages, review M2 R19).
            with zipped, remembered_facts(self.session):
                found = layout(zipped, self._skip)
                self.listed = found.listed  # archive entry → the attachment it was
                for file in found.files:
                    await self._page(zipped, file)
                for info, parts in found.attached:
                    await self._attachment(zipped, info, parts)
                await self._relink()
        details = {
            "created": self.result.created,
            "attachments": self.result.attachments,
            "skipped": len(self.result.skipped),
        }
        await record(self.session, actor, "space.imported", "space", space_id, details)
        return self.result

    def _skip(self, info: zipfile.ZipInfo, reason: str) -> None:
        self.result.skipped.append(Skipped(info.filename, reason))

    async def _page(self, zipped: zipfile.ZipFile, file: ArchiveFile) -> None:
        path = "/".join(file.slugs)
        if path in self.made:
            self._skip(file.info, "duplicate")
            return
        if await self.pages.repo(self.actor).by_path(self.space_id, path) is not None:
            self._skip(file.info, "exists")
            return
        try:
            raw = await asyncio.to_thread(
                archive.read_entry, zipped, file.info, MAX_CONTENT_CHARS * 4 + 4096
            )
        except archive.UNREADABLE:
            self._skip(file.info, "unreadable")
            return
        if raw is None:
            self._skip(file.info, "too_large")
            return
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = "\x00"
        if "\x00" in text:
            self._skip(file.info, "invalid_text")
            return
        meta, body = frontmatter.parse(text)
        if any("\x00" in v for value in meta.values() for v in strings(value)):
            self._skip(file.info, "invalid_text")  # a NUL written as a JSON escape
            return
        if len(body) > MAX_CONTENT_CHARS:
            self._skip(file.info, "too_large")
            return
        parent = await self._parents(file)
        title = page_title(meta, body, file.folders[-1])
        page = await self._create(parent, file.slugs[-1], title, body, meta.get("status"))
        tags = meta.get("tags")
        if isinstance(tags, list) and tags:
            await self._tag(page, tags)

    async def _parents(self, file: ArchiveFile) -> Page | None:
        """The page above the file's, made empty where the archive has none."""
        parent: Page | None = None
        for depth in range(1, len(file.slugs)):
            path = "/".join(file.slugs[:depth])
            page = self.made.get(path) or await self.pages.repo(self.actor).by_path(
                self.space_id, path
            )
            if page is None:
                name = file.folders[depth - 1]
                page = await self._create(parent, file.slugs[depth - 1], title_of(name), "", None)
            parent = page
        return parent

    async def _create(
        self, parent: Page | None, slug: str, title: str, body: str, status: object
    ) -> Page:
        page = await self.pages.create(
            self.actor,
            self.space_id,
            parent.id if parent else None,
            title,
            body,
            slug=slug,
            source=Source.IMPORT,
            session_key=self.session_key,
            siblings=self.siblings,
            publish=status != PageStatus.DRAFT,  # if its parent is published
        )
        self.made[page.path] = page
        self.result.created += 1
        return page

    async def _tag(self, page: Page, names: list[str]) -> None:
        clean = list(
            dict.fromkeys(n.strip() for n in names if 0 < len(n.strip()) <= MAX_TAG_NAME_CHARS)
        )
        missing = [n for n in clean if n.lower() not in self.tag_ids]
        found = await tag_repository(self.session, self.actor).usable_in(self.space_id, missing)
        for tag in sorted(found, key=lambda t: t.space_id is None):  # system tags win
            self.tag_ids[tag.name.lower()] = tag.id
        for name in missing:
            if name.lower() not in self.tag_ids:
                tag = await self.tags.create(self.actor, name, DEFAULT_COLOR, self.space_id)
                self.tag_ids[name.lower()] = tag.id
        ids = [self.tag_ids[n.lower()] for n in clean]
        await self.tags.set_on_new_page(self.actor, page, ids)

    async def _attachment(
        self, zipped: zipfile.ZipFile, info: zipfile.ZipInfo, parts: list[str]
    ) -> None:
        page = self.made.get("/".join(slugify(p, max_length=SLUG_CHARS) for p in parts[:-1]))
        if page is None:
            self._skip(info, "no_page")
            return
        try:
            attachment = await self.attachments.add(
                self.actor, page.id, parts[-1], _entry(zipped, info)
            )
        except archive.UNREADABLE:
            self._skip(info, "unreadable")
            return
        except AppError as error:
            self._skip(info, error.code.rpartition(".")[2])
            return
        self.result.attachments += 1
        old = self.listed.get("/".join([ATTACHMENTS, *parts]))
        if old is not None:
            self.new_ids[old] = attachment.id

    async def _relink(self) -> None:
        """Links to the attachments brought in point at the new ones."""
        for page in self.made.values():
            content = rewrite_links(page.content_md, self.new_ids)
            if content != page.content_md:
                await self.pages.update(
                    self.actor,
                    page.id,
                    content_md=content,
                    version=page.version,
                    source=Source.IMPORT,
                    session_key=self.session_key,
                    coalesce_seconds=_SESSION_SECONDS,
                )


async def _entry(zipped: zipfile.ZipFile, info: zipfile.ZipInfo) -> AsyncIterator[bytes]:
    handle = await asyncio.to_thread(zipped.open, info)
    try:
        while chunk := await asyncio.to_thread(handle.read, 64 * 1024):
            yield chunk
    finally:
        handle.close()
