"""Importing and exporting skills (spec 11, plan M6 decision 11).

Export: a skill as its SKILL.md (`format.serialise_skill_md`), for whoever reads it.

Import: the body is a SKILL.md or a ZIP, into the organisation (`skill.manage`) or a
space (`page.moderate` there); rights are checked before the body is read and again
after, as the wiki import does. A ZIP is read defensively by `wiki/archive.py`
(directory walked with bounded memory, no zip64, declared sizes capped, unsafe names
refused). With a virus scanner configured (`core/virus_scan.py`) the whole body is
scanned once before anything is taken (J11). Each `SKILL.md` in it (at most
`MAX_SKILL_DEPTH` path segments deep) is one skill, whose front matter name must equal
its folder's name; at most `MAX_IMPORT_SKILLS` per import, each at most
`MAX_SKILL_MD_BYTES`. Any other file is not taken: a skill here is its SKILL.md only,
and nothing of it is ever executed. Every entry that does not become a skill is reported
with a reason; an existing name in the scope is not overwritten (`exists`). One
transaction; audited as `skill.imported` (counts), each skill as `skill.created`.
"""

import asyncio
import uuid
import zipfile
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import IO

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import virus_scan
from app.core.access import Actor
from app.core.config import get_settings
from app.core.errors import Conflict
from app.core.uploads import spool
from app.modules.audit.recorder import record
from app.modules.skills import base, format
from app.modules.skills.service import SkillDraft, SkillService
from app.modules.wiki import archive

MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_IMPORT_SKILLS = 100
MAX_SKILL_DEPTH = 4  # `a/b/c/SKILL.md`
MAX_SKILL_MD_BYTES = 4 * (format.MAX_FRONTMATTER_CHARS + format.MAX_CONTENT_CHARS) + 1024
SINGLE = format.FILENAME  # the path reported for a body that is a SKILL.md itself


@dataclass(frozen=True, slots=True)
class Created:
    path: str
    skill_id: uuid.UUID
    name: str
    ignored_fields: list[str]


@dataclass(frozen=True, slots=True)
class Skipped:
    path: str
    reason: str


@dataclass
class ImportResult:
    created: list[Created] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)


class SkillTransfer:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.skills = SkillService(session)

    async def export(self, actor: Actor, skill_id: uuid.UUID) -> str:
        skill = await self.skills.get(actor, skill_id)
        return format.serialise_skill_md(skill.name, skill.description, skill.content)

    async def import_body(
        self, actor: Actor, space_id: uuid.UUID | None, stream: AsyncIterator[bytes]
    ) -> ImportResult:
        await self._allowed(actor, space_id)
        await self.session.commit()  # no pooled connection held while the body arrives
        self.actor, self.space_id = actor, space_id
        self.result = ImportResult()
        self.names: set[str] = set()
        with await spool(stream, MAX_IMPORT_BYTES, code="import.too_large") as body:
            # The optional virus scan (J11, R18-7), before the rights are read again: no
            # transaction and so no pooled connection waits while clamd works (R18-6).
            await virus_scan.scan(get_settings(), body.chunks())
            await self._allowed(actor, space_id)
            if body.head.startswith(b"PK"):
                zipped = await asyncio.to_thread(archive.open_archive, body.file)
                with zipped:
                    await self._archive(zipped)
            else:
                raw = await asyncio.to_thread(_read_all, body.file)
                if len(raw) > MAX_SKILL_MD_BYTES:
                    self._skip(SINGLE, "too_large")
                else:
                    await self._skill(SINGLE, raw, folder=None)
        details = {
            "space_id": str(space_id) if space_id else None,
            "created": len(self.result.created),
            "skipped": len(self.result.skipped),
        }
        target = ("space", space_id) if space_id else ("organization", actor.org_id)
        await record(self.session, actor, "skill.imported", target[0], target[1], details)
        return self.result

    async def _allowed(self, actor: Actor, space_id: uuid.UUID | None) -> None:
        await base.gate(self.session, actor)
        await base.require_manage(self.session, actor, space_id)

    async def _archive(self, zipped: zipfile.ZipFile) -> None:
        entries: list[tuple[zipfile.ZipInfo, list[str]]] = []
        for info in zipped.infolist():
            if info.is_dir():
                continue
            parts = archive.segments(info)
            if not parts:  # unsafe, or a name of nothing but separators and dots
                self._skip(info.filename, "unsafe_path")
            else:
                entries.append((info, parts))
        folders = {tuple(p[:-1]) for _, p in entries if p[-1] == format.FILENAME}
        count = 0
        for info, parts in entries:
            if parts[-1] != format.FILENAME:
                inside = any(tuple(parts[:n]) in folders for n in range(len(parts)))
                self._skip(info.filename, "file_unsupported" if inside else "not_in_skill")
            elif len(parts) > MAX_SKILL_DEPTH:
                self._skip(info.filename, "too_deep")
            elif count >= MAX_IMPORT_SKILLS:
                self._skip(info.filename, "too_many")
            else:
                count += 1
                try:
                    raw = await asyncio.to_thread(
                        archive.read_entry, zipped, info, MAX_SKILL_MD_BYTES
                    )
                except archive.UNREADABLE:
                    self._skip(info.filename, "unreadable")
                    continue
                if raw is None:
                    self._skip(info.filename, "too_large")
                    continue
                await self._skill(info.filename, raw, folder=parts[-2] if len(parts) > 1 else None)

    async def _skill(self, path: str, raw: bytes, folder: str | None) -> None:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = "\x00"
        if "\x00" in text:
            self._skip(path, "invalid_text")
            return
        try:
            parsed = format.parse_skill_md(text)
        except format.SkillFormatError as exc:
            self._skip(path, exc.reason)
            return
        if folder is not None and parsed.name != folder:
            self._skip(path, "name_mismatch")
            return
        if parsed.name in self.names:
            self._skip(path, "duplicate")
            return
        self.names.add(parsed.name)
        draft = SkillDraft(parsed.name, parsed.description, parsed.content, self.space_id)
        try:
            async with self.session.begin_nested():
                skill = await self.skills.create(self.actor, draft)
        except Conflict:
            self._skip(path, "exists")
            return
        self.result.created.append(Created(path, skill.id, skill.name, parsed.ignored))

    def _skip(self, path: str, reason: str) -> None:
        self.result.skipped.append(Skipped(path, reason))


def _read_all(file: IO[bytes]) -> bytes:
    file.seek(0)
    return file.read(MAX_SKILL_MD_BYTES + 1)
