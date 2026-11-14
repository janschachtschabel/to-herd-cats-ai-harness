"""Who sees which page, for every wiki service (pages, moves, trash, versions).

Rights (spec 5.3) come only from `core/access.py`:
- A page lives in a space; a space the actor cannot read does not exist for it, and
  neither do its pages (404 `page.not_found`, the same as for an unknown id). The
  repository is scoped by `visible_space_ids`, so such a page is never even loaded.
- Drafts are seen by whoever holds `page.edit` in the space; everyone else sees only
  published pages, and a draft they cannot see is 404 too.
- An agent's tool reads through `for_ai`: pages AI may read only (spec 7.3).
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, require, space_ids_with, visible_space_ids
from app.core.errors import Conflict, NotFound
from app.core.principal import Principal
from app.modules.ai.policy_filters import ai_space_ids
from app.modules.spaces.models import Space
from app.modules.wiki.models import Page, PageStatus
from app.modules.wiki.repository import PageRepository, PageScope, page_seen
from app.modules.wiki.subtree_repository import SubtreeRepository
from app.modules.wiki.versions_repository import VersionRepository


def page_not_found() -> NotFound:
    return NotFound(code="page.not_found")


def check_version(page: Page, version: int) -> None:
    if page.version != version:
        raise Conflict(code="page.version_conflict", details={"current_version": page.version})


def touch(page: Page, actor: Actor, author: Principal | None = None) -> None:
    """Record a write to the row: a new version, by the actor (or for `author`)."""
    who = author or actor.principal
    page.version += 1
    page.updated_by_type = who.type
    page.updated_by_id = who.id


class PageReader:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def repo(self, actor: Actor) -> PageRepository:
        """The actor's view of the pages: its organisation, the spaces it may read."""
        return PageRepository(self.session, self.scope(actor))

    def subtree(self, actor: Actor) -> SubtreeRepository:
        """`repo`, with the statements over whole subtrees."""
        return SubtreeRepository(self.session, self.scope(actor))

    def versions(self, actor: Actor) -> VersionRepository:
        """The versions of the pages in `repo`."""
        return VersionRepository(self.session, self.scope(actor))

    def scope(self, actor: Actor) -> PageScope:
        """The actor's organisation and the spaces it may read (SQL)."""
        return PageScope(actor.org_id, visible_space_ids(actor))

    def seen(self, actor: Actor) -> ColumnElement[bool]:
        """The pages the actor sees, as SQL for other modules' lists (the same rule as
        `readable`, for many pages at once)."""
        return page_seen(
            actor.org_id, visible_space_ids(actor), space_ids_with(actor, Action.PAGE_EDIT)
        )

    async def titles(self, actor: Actor, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
        """The titles of those of the pages the actor sees."""
        return await self.repo(actor).titles(ids, space_ids_with(actor, Action.PAGE_EDIT))

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

    async def for_ai(self, actor: Actor, page_id: uuid.UUID) -> Page:
        """`readable`, for an agent's tool (spec 7.3): also 404 for a page locked for AI
        (`no_ai`) or in a space whose policy is `none`, both in the statement that
        applies the rights. Whether the run's connection may receive the page is the
        run's check, before its next model call."""
        scope = PageScope(
            actor.org_id,
            visible_space_ids(actor).where(Space.id.in_(ai_space_ids(actor.org_id))),
        )
        page = await PageRepository(self.session, scope).live(page_id, ai=True)
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
