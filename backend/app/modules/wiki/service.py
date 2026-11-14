"""Wiki pages: creation, reading, editing with optimistic locking, publishing; moves
(`moves.py`) and the trash (`trash.py`) behind the same service. Who sees what:
`visibility.py`. `page.publish` publishes any draft; `page.edit` one's own.

Every ancestor of a published page is published: publishing below a draft, and moving
or restoring published pages below one, answer 409 `page.parent_draft`. So whoever
sees a page also sees its parent.

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
from app.modules.tags.models import SubjectType
from app.modules.tags.repository import tag_repository
from app.modules.wiki.authorship import Authorship
from app.modules.wiki.events import PAGE_CREATED, PAGE_PUBLISHED, page_event
from app.modules.wiki.models import MAX_DEPTH, Page, PageStatus, VersionSource
from app.modules.wiki.moves import PageMoves
from app.modules.wiki.siblings import Siblings
from app.modules.wiki.trash import PageTrash
from app.modules.wiki.tree import child_path, depth_of, unique_slug
from app.modules.wiki.versions import VersionService
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
        self,
        actor: Actor,
        space_id: uuid.UUID,
        params: PageParams,
        *,
        tag_id: uuid.UUID | None = None,
    ) -> pagination.Page[Page]:
        """The space's pages outside the trash, flat, by path (parents first); each
        carries `parent_id` and `sort_order` for nesting and ordering siblings. With
        `tag_id`, only the pages carrying that tag."""
        await require(self.session, actor, Action.SPACE_READ, space_id)
        drafts = await can(self.session, actor, Action.PAGE_EDIT, space_id)
        after = decode_key_cursor(params.cursor) if params.cursor else None
        tagged = None
        if tag_id is not None:
            tagged = tag_repository(self.session, actor).subject_ids(SubjectType.PAGE, [tag_id])
        rows = await self.repo(actor).tree_page(
            space_id, drafts=drafts, after=after, limit=params.limit + 1, among=tagged
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
        *,
        slug: str | None = None,
        source: VersionSource = VersionSource.HUMAN,
        session_key: str | None = None,
        siblings: Siblings | None = None,
        publish: bool = False,
        by: Authorship | None = None,
    ) -> Page:
        """A new draft at the end of its siblings. Its slug comes from `slug` if given
        (an imported file's name), else from the title; a sibling's slug gets a suffix.
        `session_key` lets later saves of the same session fold into its first version.
        `siblings` remembers slugs and order per parent across many creations. With
        `publish`, it is published at once if its parent is (or it has none): its
        creator may publish an own draft, as `publish` allows. `by`: written for an
        agent (`authorship.py`), which becomes the page's creator."""
        await require(self.session, actor, Action.PAGE_CREATE, space_id)
        pages = self.repo(actor)
        siblings = siblings or Siblings()
        await siblings.lock(pages, space_id)
        parent_path = None
        if parent_id is not None:
            parent = await siblings.parent(pages, space_id, parent_id)
            if parent is None:
                raise ValidationFailed(code="page.parent_not_found")
            if depth_of(parent.path) >= MAX_DEPTH:
                raise ValidationFailed(code="page.too_deep")
            parent_path = parent.path
            publish = publish and parent.status == PageStatus.PUBLISHED
        taken = await siblings.slugs(pages, space_id, parent_id)
        slug = unique_slug(slug or title, taken)
        sort_order = await siblings.next_order(pages, space_id, parent_id)
        taken.add(slug)
        who = by.principal if by else actor.principal
        page = await pages.add(
            Page(
                org_id=actor.org_id,
                space_id=space_id,
                parent_id=parent_id,
                title=title,
                slug=slug,
                path=child_path(parent_path, slug),
                sort_order=sort_order,
                content_md=content_md,
                status=PageStatus.PUBLISHED if publish else PageStatus.DRAFT,
                published_at=utcnow() if publish else None,
                created_by_type=who.type,
                created_by_id=who.id,
                updated_by_type=who.type,
                updated_by_id=who.id,
            )
        )
        await VersionService(self.session).record(
            page, actor, source, session_key=session_key, first=True, by=by
        )
        details = {"space_id": str(space_id), "path": page.path}
        await record(self.session, actor, "page.created", "page", page.id, details)
        timeline = source != VersionSource.IMPORT  # an import emits no events
        if timeline:
            await page_event(self.session, actor, PAGE_CREATED, page)
        if publish:
            await record(self.session, actor, "page.published", "page", page.id)
            if timeline:
                await page_event(self.session, actor, PAGE_PUBLISHED, page)
        return page

    async def update(
        self,
        actor: Actor,
        page_id: uuid.UUID,
        *,
        title: str | None = None,
        content_md: str | None = None,
        version: int,
        change_summary: str | None = None,
        source: VersionSource = VersionSource.HUMAN,
        session_key: str | None = None,
        coalesce_seconds: int = 0,
        by: Authorship | None = None,
    ) -> Page:
        """Change title and/or content, saved as a new version (folded into the newest
        one of the same session, see `VersionService.record`); a request that changes
        nothing changes nothing. A content change ends the page's live sessions. `by`:
        written for an agent (`authorship.py`)."""
        page = await self.readable(actor, page_id, lock=True)
        await self.reader.require_in_space(actor, Action.PAGE_EDIT, page)
        check_version(page, version)
        changed = False
        if title is not None and title != page.title:
            page.title, changed = title, True
        if content_md is not None and content_md != page.content_md:
            page.content_md, changed = content_md, True
            page.collab_generation += 1  # saved outside the live session: it ends
        if changed:
            touch(page, actor, by.principal if by else None)
            await self.session.flush()
            await VersionService(self.session).record(
                page,
                actor,
                source,
                change_summary=change_summary,
                session_key=session_key,
                coalesce_seconds=coalesce_seconds,
                by=by,
            )
        return page

    async def save_live(
        self, editors: list[Actor], page: Page, content_md: str, *, session_key: str
    ) -> Page:
        """Content from the page's live session, edited by `editors`: saved without
        ending the session (the generation stays). The caller (`collab_service`) holds
        the page row lock and has checked the generation and every editor's rights."""
        if content_md == page.content_md:
            return page
        page.content_md = content_md
        _, author = await VersionService(self.session).record_live(page, editors, session_key)
        touch(page, author)
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
        if page.parent_id is not None:
            # The parent cannot turn back into a draft (there is no unpublish), and a
            # move of this page waits for the row lock held here.
            parent = await self.repo(actor).live_in_space(page.space_id, page.parent_id)
            if parent is None or parent.status != PageStatus.PUBLISHED:
                raise Conflict(code="page.parent_draft")
        page.status = PageStatus.PUBLISHED
        page.published_at = utcnow()
        touch(page, actor)
        await self.session.flush()
        await record(self.session, actor, "page.published", "page", page.id)
        await page_event(self.session, actor, PAGE_PUBLISHED, page)
        return page
