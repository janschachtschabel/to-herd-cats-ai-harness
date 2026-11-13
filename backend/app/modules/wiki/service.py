"""Wiki pages: creation, reading, editing with optimistic locking, publishing.

Rights (spec 5.3) come only from `core/access.py`:
- A page lives in a space; a space the actor cannot read does not exist for it, and
  neither do its pages (404 `page.not_found`, the same as for an unknown id).
- Drafts are seen by whoever holds `page.edit` in the space; everyone else sees only
  published pages, and a draft they cannot see is 404 too.
- `page.publish` publishes any draft; `page.edit` publishes one's own.

Slugs stay when a page is renamed, so addresses are stable; they change only when a
page moves next to a sibling with the same slug (`moves.py`).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, can, require, visible_space_ids
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.models_base import utcnow
from app.core.pagination import PageParams, decode_key_cursor, encode_key_cursor
from app.modules.audit.recorder import record
from app.modules.wiki.models import MAX_DEPTH, Page, PageStatus
from app.modules.wiki.repository import PageRepository, PageScope
from app.modules.wiki.tree import child_path, depth_of, unique_slug


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


class PageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def repo(self, actor: Actor) -> PageRepository:
        """The actor's view of the pages: its organisation, the spaces it may read."""
        return PageRepository(self.session, PageScope(actor.org_id, visible_space_ids(actor)))

    # --- reading -------------------------------------------------------------------

    async def get(self, actor: Actor, page_id: uuid.UUID) -> Page:
        return await self.readable(actor, page_id)

    async def get_by_path(self, actor: Actor, space_id: uuid.UUID, path: str) -> Page:
        await require(self.session, actor, Action.SPACE_READ, space_id)
        page = await self.repo(actor).by_path(space_id, path)
        if page is None or not await self._may_see(actor, page):
            raise page_not_found()
        return page

    async def tree(
        self, actor: Actor, space_id: uuid.UUID, params: PageParams
    ) -> pagination.Page[Page]:
        """The space's pages outside the trash, flat, by path (parents first); each
        carries `parent_id` and `sort_order` for nesting and ordering siblings."""
        await require(self.session, actor, Action.SPACE_READ, space_id)
        drafts = await can(self.session, actor, Action.PAGE_EDIT, space_id)
        after = decode_key_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).tree_page(
            space_id, drafts=drafts, after=after, limit=params.limit + 1
        )
        items = rows[: params.limit]
        more = len(rows) > params.limit
        cursor = encode_key_cursor(items[-1].path, items[-1].id) if more else None
        return pagination.Page[Page](items=items, next_cursor=cursor)

    async def readable(self, actor: Actor, page_id: uuid.UUID, *, lock: bool = False) -> Page:
        """The page if the actor may see it, else 404; `lock` as in `live`."""
        page = await self.repo(actor).live(page_id, lock=lock)
        if page is None:
            raise page_not_found()
        try:
            # Also notes an admin's look into a team or personal space (spec 5.5).
            await require(self.session, actor, Action.SPACE_READ, page.space_id)
        except NotFound:
            raise page_not_found() from None
        if not await self._may_see(actor, page):
            raise page_not_found()
        return page

    async def _may_see(self, actor: Actor, page: Page) -> bool:
        if page.status == PageStatus.PUBLISHED:
            return True
        return await can(self.session, actor, Action.PAGE_EDIT, page.space_id)

    # --- writing -------------------------------------------------------------------

    async def create(
        self,
        actor: Actor,
        space_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        title: str,
        content_md: str = "",
    ) -> Page:
        """A new draft at the end of its siblings."""
        await require(self.session, actor, Action.PAGE_CREATE, space_id)
        pages = self.repo(actor)
        await pages.lock_tree(space_id)
        parent_path = None
        if parent_id is not None:
            parent = await pages.live_in_space(space_id, parent_id)
            if parent is None:
                raise ValidationFailed(code="page.parent_not_found")
            if depth_of(parent.path) >= MAX_DEPTH:
                raise ValidationFailed(code="page.too_deep")
            parent_path = parent.path
        slug = unique_slug(title, await pages.sibling_slugs(space_id, parent_id))
        who = actor.principal
        page = await pages.add(
            Page(
                org_id=actor.org_id,
                space_id=space_id,
                parent_id=parent_id,
                title=title,
                slug=slug,
                path=child_path(parent_path, slug),
                sort_order=await pages.next_sort_order(space_id, parent_id),
                content_md=content_md,
                status=PageStatus.DRAFT,
                created_by_type=who.type,
                created_by_id=who.id,
                updated_by_type=who.type,
                updated_by_id=who.id,
            )
        )
        details = {"space_id": str(space_id), "path": page.path}
        await record(self.session, actor, "page.created", "page", page.id, details)
        return page

    async def update(
        self,
        actor: Actor,
        page_id: uuid.UUID,
        *,
        title: str | None = None,
        content_md: str | None = None,
        version: int,
    ) -> Page:
        """Change title and/or content; a request that changes nothing changes nothing."""
        page = await self.readable(actor, page_id, lock=True)
        await require(self.session, actor, Action.PAGE_EDIT, page.space_id)
        check_version(page, version)
        changed = False
        if title is not None and title != page.title:
            page.title, changed = title, True
        if content_md is not None and content_md != page.content_md:
            page.content_md, changed = content_md, True
        if changed:
            touch(page, actor)
            await self.session.flush()
        return page

    async def publish(self, actor: Actor, page_id: uuid.UUID, version: int) -> Page:
        page = await self.readable(actor, page_id, lock=True)
        own = (page.created_by_type, page.created_by_id) == (
            actor.principal.type,
            actor.principal.id,
        )
        if not await can(self.session, actor, Action.PAGE_PUBLISH, page.space_id):
            if not own:  # an own draft needs `page.edit`, which seeing it already proved
                raise Forbidden(code="auth.permission_denied")
        check_version(page, version)
        if page.status == PageStatus.PUBLISHED:
            raise Conflict(code="page.already_published")
        page.status = PageStatus.PUBLISHED
        page.published_at = utcnow()
        touch(page, actor)
        await self.session.flush()
        await record(self.session, actor, "page.published", "page", page.id)
        return page
