"""Who sees which page, for every wiki service (pages, moves, trash, versions).

Rights (spec 5.3) come only from `core/access.py`:
- A page lives in a space; a space the actor cannot read does not exist for it, and
  neither do its pages (404 `page.not_found`, the same as for an unknown id). The
  repository is scoped by `visible_space_ids`, so such a page is never even loaded.
- Drafts are seen by whoever holds `page.edit` in the space; everyone else sees only
  published pages, and a draft they cannot see is 404 too.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, require, visible_space_ids
from app.core.errors import Conflict, NotFound
from app.modules.wiki.models import Page, PageStatus
from app.modules.wiki.repository import PageRepository, PageScope
from app.modules.wiki.subtree_repository import SubtreeRepository


def page_not_found() -> NotFound:
    return NotFound(code="page.not_found")


def check_version(page: Page, version: int) -> None:
    if page.version != version:
        raise Conflict(code="page.version_conflict", details={"current_version": page.version})


def touch(page: Page, actor: Actor) -> None:
    """Record a write to the row: a new version, by the actor."""
    page.version += 1
    page.updated_by_type = actor.principal.type
    page.updated_by_id = actor.principal.id


class PageReader:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def repo(self, actor: Actor) -> PageRepository:
        """The actor's view of the pages: its organisation, the spaces it may read."""
        return PageRepository(self.session, self._scope(actor))

    def subtree(self, actor: Actor) -> SubtreeRepository:
        """`repo`, with the statements over whole subtrees."""
        return SubtreeRepository(self.session, self._scope(actor))

    def _scope(self, actor: Actor) -> PageScope:
        return PageScope(actor.org_id, visible_space_ids(actor))

    async def readable(self, actor: Actor, page_id: uuid.UUID, *, lock: bool = False) -> Page:
        """The page outside the trash if the actor may see it, else 404; with `lock`,
        as committed now and locked until the transaction ends."""
        page = await self.repo(actor).live(page_id, lock=lock)
        if page is None:
            raise page_not_found()
        await self.require_in_space(actor, Action.SPACE_READ, page)
        if not await self.may_see(actor, page):
            raise page_not_found()
        return page

    async def may_see(self, actor: Actor, page: Page) -> bool:
        if page.status == PageStatus.PUBLISHED:
            return True
        return await can(self.session, actor, Action.PAGE_EDIT, page.space_id)

    async def require_in_space(self, actor: Actor, action: Action, page: Page) -> None:
        """`require` in the page's space, where a space gone from view hides the page.
        Also notes an admin's look into a team or personal space (spec 5.5)."""
        try:
            await require(self.session, actor, action, page.space_id)
        except NotFound:
            raise page_not_found() from None
