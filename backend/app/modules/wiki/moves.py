"""Moving pages in the tree: a new parent (in the same space), a place among the
siblings, and the paths of the whole subtree rewritten in the same transaction.

Every move holds the space's tree lock and re-reads what it decides on, so two moves
that would each be fine alone but together make a cycle (A under B, B under A) are
decided one after the other: the second sees the first and answers 409.

Published pages do not go below a draft (409 `page.parent_draft`): whoever sees a page
sees its parent.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor
from app.core.errors import Conflict, ValidationFailed
from app.modules.audit.recorder import record
from app.modules.wiki.models import MAX_DEPTH, Page, PageStatus
from app.modules.wiki.subtree_repository import SubtreeRepository
from app.modules.wiki.tree import child_path, depth_of, unique_slug
from app.modules.wiki.visibility import PageReader, check_version, page_not_found, touch


class PageMoves:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = PageReader(session)

    async def move(
        self,
        actor: Actor,
        page_id: uuid.UUID,
        *,
        new_parent_id: uuid.UUID | None,
        position: int | None,
        version: int,
    ) -> Page:
        """Under `new_parent_id` (None: the top level), at `position` among the
        siblings (0 first; None: at the end, or where it is if the parent stays)."""
        page = await self.reader.readable(actor, page_id)
        await self.reader.require_in_space(actor, Action.PAGE_EDIT, page)
        pages = self.reader.subtree(actor)
        await pages.lock_tree(page.space_id)
        locked = await pages.live(page_id, lock=True)
        if locked is None:
            raise page_not_found()
        page = locked
        check_version(page, version)
        old_path = page.path
        reparent = new_parent_id != page.parent_id
        if reparent:
            await self._reparent(pages, page, new_parent_id)
        await self._place(pages, page, position, append=reparent)
        page.collab_generation += 1
        touch(page, actor)
        await self.session.flush()
        details = {"from": old_path, "to": page.path}
        await record(self.session, actor, "page.moved", "page", page.id, details)
        return page

    async def _reparent(
        self, pages: SubtreeRepository, page: Page, new_parent_id: uuid.UUID | None
    ) -> None:
        parent_path = None
        if new_parent_id is not None:
            parent = await pages.live(new_parent_id)
            if parent is None:
                raise ValidationFailed(code="page.parent_not_found")
            if parent.space_id != page.space_id:
                raise ValidationFailed(code="page.move_other_space")
            if parent.id == page.id or parent.path.startswith(f"{page.path}/"):
                raise Conflict(code="page.move_cycle")
            if parent.status != PageStatus.PUBLISHED and await pages.published_at_or_below(
                page.space_id, page.path
            ):
                raise Conflict(code="page.parent_draft")
            parent_path = parent.path
        taken = await pages.sibling_slugs(page.space_id, new_parent_id)
        slug = unique_slug(page.slug, taken) if page.slug in taken else page.slug
        new_path = child_path(parent_path, slug)
        deepest = await pages.deepest_at_or_below(page.space_id, page.path)
        if deepest - depth_of(page.path) + depth_of(new_path) > MAX_DEPTH:
            raise ValidationFailed(code="page.too_deep")
        old_path = page.path
        page.parent_id, page.slug, page.path = new_parent_id, slug, new_path
        await self.session.flush()  # the page first: its descendants follow it
        await pages.rewrite_descendant_paths(page.space_id, old_path, new_path)

    async def _place(
        self, pages: SubtreeRepository, page: Page, position: int | None, *, append: bool
    ) -> None:
        """Renumber the siblings 0, 1, … with the page at `position`."""
        if position is None and not append:
            return
        siblings = [p for p in await pages.children(page.space_id, page.parent_id) if p is not page]
        at = len(siblings) if position is None else min(position, len(siblings))
        siblings.insert(at, page)
        for index, sibling in enumerate(siblings):
            sibling.sort_order = index
