"""Page versions: every save is one (spec 9), numbered per page; a restore brings an
older state back as a new version and ends live sessions; labels name a version.

The history (list, read, diff), labels and restores need `page.edit` on the page
(review M2 R16): viewers see the current published content only, never the
draft-time versions or their authors. A diff compares at most `HERD_DIFF_MAX_LINES` lines
(both versions together; its cost grows with them): more is 422 `page.diff_too_large`.
"""

import asyncio
import builtins
import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor
from app.core.config import get_settings
from app.core.errors import NotFound, ValidationFailed
from app.core.models_base import utcnow
from app.core.pagination import PageParams, decode_id_cursor, id_page
from app.modules.audit.recorder import record
from app.modules.wiki import diffing
from app.modules.wiki.models import Page, PageVersion, VersionSource
from app.modules.wiki.versions_repository import NamedVersion
from app.modules.wiki.visibility import PageReader, check_version, touch

LIVE_COALESCE_SECONDS = 60


def _not_found() -> NotFound:
    return NotFound(code="page.version_not_found")


class VersionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = PageReader(session)

    async def record(
        self,
        page: Page,
        actor: Actor,
        source: VersionSource,
        *,
        change_summary: str | None = None,
        session_key: str | None = None,
        coalesce_seconds: int = 0,
        first: bool = False,
    ) -> PageVersion:
        """The page's title and content as its next version, by the actor. The caller
        has checked the actor's rights and holds the page row (`readable(lock=True)`,
        or a page it has just created), which also orders the numbers.

        With `coalesce_seconds`, a save of the same author, source and `session_key`
        overwrites the newest version while that is younger than the window (counted
        from when it was first written); without a session key nothing is folded.
        `first`: the page has just been created and has no version yet."""
        versions = self.reader.versions(actor)
        latest = None if first else await versions.latest(page.id)
        if latest is not None and _folds_into(latest, actor, source, session_key, coalesce_seconds):
            latest.title, latest.content_md = page.title, page.content_md
            if change_summary is not None:
                latest.change_summary = change_summary
            await self.session.flush()
            return latest
        return await versions.add(
            PageVersion(
                org_id=page.org_id,
                page_id=page.id,
                number=latest.number + 1 if latest else 1,
                title=page.title,
                content_md=page.content_md,
                author_type=actor.principal.type,
                author_id=actor.principal.id,
                source=source,
                change_summary=change_summary,
                session_key=session_key,
            )
        )

    async def record_live(
        self, page: Page, editors: builtins.list[Actor], session_key: str
    ) -> tuple[PageVersion, Actor]:
        """A save from a live session edited by `editors` (in order of their edits):
        folded into the newest version while that is one of this session, younger
        than 60 s and by one of the editors; otherwise a new version by the first.
        The author too, for the page's `updated_by`. Same lock rule as `record`."""
        latest = await self.reader.versions(editors[0]).latest(page.id)
        author = editors[0]
        if latest is not None:
            for editor in editors:
                if _folds_into(
                    latest, editor, VersionSource.COLLAB, session_key, LIVE_COALESCE_SECONDS
                ):
                    author = editor
                    break
        version = await self.record(
            page,
            author,
            VersionSource.COLLAB,
            session_key=session_key,
            coalesce_seconds=LIVE_COALESCE_SECONDS,
        )
        return version, author

    async def _editable(self, actor: Actor, page_id: uuid.UUID) -> Page:
        """The page, if the actor may see it (404 otherwise) and edit it (403)."""
        page = await self.reader.readable(actor, page_id)
        await self.reader.require_in_space(actor, Action.PAGE_EDIT, page)
        return page

    async def list(
        self, actor: Actor, page_id: uuid.UUID, params: PageParams
    ) -> pagination.Page[NamedVersion]:
        """Newest first."""
        page = await self._editable(actor, page_id)
        before = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.reader.versions(actor).page(page.id, before, params.limit + 1)
        return id_page(rows, params.limit, lambda row: row.version.id)

    async def get(self, actor: Actor, page_id: uuid.UUID, number: int) -> NamedVersion:
        page = await self._editable(actor, page_id)
        found = await self.reader.versions(actor).get(page.id, number)
        if found is None:
            raise _not_found()
        return found

    async def label(
        self, actor: Actor, page_id: uuid.UUID, number: int, label: str | None
    ) -> NamedVersion:
        """Name a version (None: take the name away)."""
        page = await self._editable(actor, page_id)
        found = await self.reader.versions(actor).get(page.id, number)
        if found is None:
            raise _not_found()
        found.version.label = label
        await self.session.flush()
        return found

    async def diff(
        self, actor: Actor, page_id: uuid.UUID, from_number: int, to_number: int
    ) -> diffing.Diff:
        page = await self._editable(actor, page_id)
        versions = self.reader.versions(actor)
        old, new = await versions.get(page.id, from_number), await versions.get(page.id, to_number)
        if old is None or new is None:
            raise _not_found()
        a, b = old.version, new.version
        if _lines(a.content_md) + _lines(b.content_md) > get_settings().diff_max_lines:
            raise ValidationFailed(code="page.diff_too_large")
        return await asyncio.to_thread(diffing.diff, a.title, a.content_md, b.title, b.content_md)

    async def restore(self, actor: Actor, page_id: uuid.UUID, number: int, version: int) -> Page:
        """The content of version `number` becomes the page's content again, as a new
        version; title, path and status stay. Ends live sessions of the page."""
        page = await self.reader.readable(actor, page_id, lock=True)
        await self.reader.require_in_space(actor, Action.PAGE_EDIT, page)
        check_version(page, version)
        found = await self.reader.versions(actor).get(page.id, number)
        if found is None:
            raise _not_found()
        page.content_md = found.version.content_md
        page.collab_generation += 1
        touch(page, actor)
        await self.session.flush()
        await self.record(page, actor, VersionSource.RESTORE, change_summary=f"restore:{number}")
        details = {"number": number}
        await record(self.session, actor, "page.version_restored", "page", page.id, details)
        return page


def _lines(text: str) -> int:
    return text.count("\n") + 1


def _folds_into(
    latest: PageVersion,
    actor: Actor,
    source: VersionSource,
    session_key: str | None,
    coalesce_seconds: int,
) -> bool:
    return (
        coalesce_seconds > 0
        and session_key is not None
        and latest.session_key == session_key
        and latest.source == source
        and (latest.author_type, latest.author_id) == (actor.principal.type, actor.principal.id)
        and utcnow() - latest.created_at < timedelta(seconds=coalesce_seconds)
    )
