"""The trash instead of deleting (spec 9): a page goes into the trash with every page
below it, at one time; a restore brings back the page and those that went with it.
Deleting for good (`purge`) is for system admins only and takes a page from the trash
with everything below it, its versions, tags and attachments included.

Moderators trash and restore (`page.trash`); the trash lists the pages that went in
on their own or as the top of a batch. Like moves, every change holds the space's
tree lock.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, can, require
from app.core.errors import Conflict, ValidationFailed
from app.core.models_base import utcnow
from app.core.pagination import PageParams, decode_cursor, encode_cursor
from app.modules.audit.recorder import record
from app.modules.tags.models import SubjectType
from app.modules.tags.repository import tag_repository
from app.modules.wiki.attachments import AttachmentService
from app.modules.wiki.events import PAGE_RESTORED, PAGE_TRASHED, page_event
from app.modules.wiki.models import MAX_DEPTH, Page, PageStatus
from app.modules.wiki.subtree_repository import SubtreeRepository
from app.modules.wiki.tree import child_path, depth_of
from app.modules.wiki.visibility import PageReader, check_version, page_not_found, touch


class PageTrash:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = PageReader(session)

    async def trash(self, actor: Actor, page_id: uuid.UUID, version: int) -> None:
        page = await self.reader.readable(actor, page_id)
        await self.reader.require_in_space(actor, Action.PAGE_TRASH, page)
        pages = self.reader.subtree(actor)
        await pages.lock_tree(page.space_id)
        locked = await pages.live(page_id, lock=True)
        if locked is None:
            raise page_not_found()
        check_version(locked, version)
        count = await pages.trash_at_or_below(locked.space_id, locked.path, utcnow())
        await record(self.session, actor, "page.trashed", "page", page_id, {"pages": count})
        await page_event(self.session, actor, PAGE_TRASHED, locked)

    async def restore(self, actor: Actor, page_id: uuid.UUID) -> Page:
        """Back to its parent if that is outside the trash, else to the top level;
        409 `page.path_taken` if a page holds that path now, 409 `page.parent_draft`
        if published pages would come back below a draft."""
        pages = self.reader.subtree(actor)
        page = await self._trashed(actor, pages, page_id)
        await self.reader.require_in_space(actor, Action.PAGE_TRASH, page)
        await pages.lock_tree(page.space_id)
        page = await self._trashed(actor, pages, page_id)  # as the writers before left it
        below = await pages.trashed_with(page)
        parent = None
        if page.parent_id is not None:
            parent = await pages.live_in_space(page.space_id, page.parent_id)
        published = any(p.status == PageStatus.PUBLISHED for p in [page, *below])
        if parent is not None and parent.status != PageStatus.PUBLISHED and published:
            raise Conflict(code="page.parent_draft")
        new_path = child_path(parent.path if parent else None, page.slug)
        if await pages.by_path(page.space_id, new_path) is not None:
            raise Conflict(code="page.path_taken")
        deepest = max(depth_of(p.path) for p in [page, *below])
        if deepest - depth_of(page.path) + depth_of(new_path) > MAX_DEPTH:
            raise ValidationFailed(code="page.too_deep")
        old_path = page.path
        page.parent_id = parent.id if parent else None
        page.sort_order = await pages.next_sort_order(page.space_id, page.parent_id)
        page.path = new_path
        page.trashed_at = None
        page.collab_generation += 1
        touch(page, actor)
        await self.session.flush()
        await pages.restore_below([p.id for p in below], old_path, new_path)
        details = {"pages": 1 + len(below)}
        await record(self.session, actor, "page.restored", "page", page.id, details)
        await page_event(self.session, actor, PAGE_RESTORED, page)
        return page

    async def list(
        self, actor: Actor, space_id: uuid.UUID, params: PageParams
    ) -> pagination.Page[Page]:
        await require(self.session, actor, Action.PAGE_TRASH, space_id)
        before = decode_cursor(params.cursor) if params.cursor else None
        rows = await self.reader.subtree(actor).trash_roots(space_id, before, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        last = items[-1] if more else None
        cursor = encode_cursor(last.trashed_at, last.id) if last and last.trashed_at else None
        return pagination.Page[Page](items=items, next_cursor=cursor)

    async def purge(self, actor: Actor, page_id: uuid.UUID) -> None:
        await require(self.session, actor, Action.PAGE_PURGE)
        pages = self.reader.subtree(actor)
        page = await pages.trashed(page_id)
        if page is None:
            if await pages.live(page_id) is not None:
                raise Conflict(code="page.not_trashed")
            raise page_not_found()
        await pages.lock_tree(page.space_id)
        if await pages.trashed(page_id) is None:  # restored or purged meanwhile
            raise page_not_found()
        await AttachmentService(self.session).purge_pages(
            actor, await pages.ids_at_or_below(page_id)
        )
        purged = await pages.delete_subtree(page_id)
        await tag_repository(self.session, actor).delete_for(SubjectType.PAGE, purged)
        details = {"title": page.title, "path": page.path, "pages": len(purged)}
        await record(self.session, actor, "page.purged", "page", page_id, details)

    async def _trashed(self, actor: Actor, pages: SubtreeRepository, page_id: uuid.UUID) -> Page:
        """A page in the trash, for those who may see drafts in its space."""
        page = await pages.trashed(page_id)
        if page is None:
            raise page_not_found()
        await self.reader.require_in_space(actor, Action.SPACE_READ, page)
        if not await can(self.session, actor, Action.PAGE_EDIT, page.space_id):
            raise page_not_found()
        return page
