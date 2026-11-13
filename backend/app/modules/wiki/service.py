"""Wiki pages: creation, reading, editing with optimistic locking, publishing; moves
(`moves.py`) and the trash (`trash.py`) behind the same service. Who sees what:
`visibility.py`. `page.publish` publishes any draft; `page.edit` one's own.

Slugs stay when a page is renamed, so addresses are stable; they change only when a
page moves next to a sibling with the same slug (`moves.py`).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, can, require
from app.core.errors import Conflict, Forbidden, ValidationFailed
from app.core.models_base import utcnow
from app.core.pagination import PageParams, decode_key_cursor, encode_key_cursor
from app.modules.audit.recorder import record
from app.modules.wiki.models import MAX_DEPTH, Page, PageStatus
from app.modules.wiki.moves import PageMoves
from app.modules.wiki.trash import PageTrash
from app.modules.wiki.tree import child_path, depth_of, unique_slug
from app.modules.wiki.visibility import PageReader, check_version, page_not_found, touch


class PageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = PageReader(session)
        self.repo = self.reader.repo
        self.readable = self.reader.readable

    # --- reading -------------------------------------------------------------------

    async def get(self, actor: Actor, page_id: uuid.UUID) -> Page:
        return await self.readable(actor, page_id)

    async def get_by_path(self, actor: Actor, space_id: uuid.UUID, path: str) -> Page:
        await require(self.session, actor, Action.SPACE_READ, space_id)
        page = await self.repo(actor).by_path(space_id, path)
        if page is None or not await self.reader.may_see(actor, page):
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

    # --- the tree and the trash ----------------------------------------------------

    async def move(
        self,
        actor: Actor,
        page_id: uuid.UUID,
        *,
        new_parent_id: uuid.UUID | None,
        position: int | None,
        version: int,
    ) -> Page:
        return await PageMoves(self.session).move(
            actor, page_id, new_parent_id=new_parent_id, position=position, version=version
        )

    async def trash(self, actor: Actor, page_id: uuid.UUID, version: int) -> None:
        await PageTrash(self.session).trash(actor, page_id, version)

    async def restore_from_trash(self, actor: Actor, page_id: uuid.UUID) -> Page:
        return await PageTrash(self.session).restore(actor, page_id)

    async def list_trash(
        self, actor: Actor, space_id: uuid.UUID, params: PageParams
    ) -> pagination.Page[Page]:
        return await PageTrash(self.session).list(actor, space_id, params)

    async def purge(self, actor: Actor, page_id: uuid.UUID) -> None:
        await PageTrash(self.session).purge(actor, page_id)

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
        await self.reader.require_in_space(actor, Action.PAGE_EDIT, page)
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
