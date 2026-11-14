"""The SQL of wiki pages. Every statement is scoped by the actor's organisation and the
spaces it may read (`PageScope`, built from `access.visible_space_ids`), so a page in a
space the actor cannot see is never even loaded. Statements over whole subtrees (moves,
the trash, purging) are in `subtree_repository.py`.

Reads refresh rows already in the session (`populate_existing`): subtree statements
change rows in bulk, behind the session's back."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, and_, false, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.wiki.models import Page, PageStatus


@dataclass(frozen=True, slots=True)
class PageScope:
    org_id: uuid.UUID
    space_ids: Select[uuid.UUID]  # the spaces the actor may read (SQL)


def under(parent_id: uuid.UUID | None) -> ColumnElement[bool]:
    """The children of `parent_id`; the top level for None (index-friendly)."""
    return Page.parent_id.is_(None) if parent_id is None else Page.parent_id == parent_id


def page_seen(
    org_id: uuid.UUID, readable: Select[uuid.UUID], drafts: Select[uuid.UUID]
) -> ColumnElement[bool]:
    """The pages an actor sees, as SQL: of its organisation, in a space it may read
    (`readable`), outside the trash, and published or in a space where it may see
    drafts (`drafts`, where it holds `page.edit`)."""
    return and_(
        Page.org_id == org_id,
        Page.space_id.in_(readable),
        Page.trashed_at.is_(None),
        or_(Page.status == PageStatus.PUBLISHED, Page.space_id.in_(drafts)),
    )


class PageRepository:
    def __init__(self, session: AsyncSession, scope: PageScope) -> None:
        self.session = session
        self.scope = scope

    def _scoped(self) -> ColumnElement[bool]:
        return and_(Page.org_id == self.scope.org_id, Page.space_id.in_(self.scope.space_ids))

    def _live(self) -> ColumnElement[bool]:
        return and_(self._scoped(), Page.trashed_at.is_(None))

    async def add(self, page: Page) -> Page:
        self.session.add(page)
        await self.session.flush()
        return page

    async def lock_tree(self, space_id: uuid.UUID) -> None:
        """Serialise changes to the space's tree (create, move, trash, restore, purge)
        until the transaction ends: paths, slugs and cycles are decided on what the
        writers before have committed."""
        await advisory_xact_lock(self.session, f"wiki.tree:{space_id}")

    async def live(
        self, page_id: uuid.UUID, *, lock: bool = False, ai: bool = False
    ) -> Page | None:
        """A page outside the trash; with `lock`, the row as committed now, locked
        until the transaction ends; with `ai`, only if it is not locked for AI
        (`no_ai`, in the same statement)."""
        stmt = (
            select(Page)
            .where(self._live(), Page.id == page_id)
            .execution_options(populate_existing=True)
        )
        if ai:
            stmt = stmt.where(Page.no_ai.is_(false()))
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def live_in_space(self, space_id: uuid.UUID, page_id: uuid.UUID) -> Page | None:
        stmt = (
            select(Page)
            .where(self._live(), Page.space_id == space_id, Page.id == page_id)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def by_path(self, space_id: uuid.UUID, path: str) -> Page | None:
        stmt = (
            select(Page)
            .where(self._live(), Page.space_id == space_id, Page.path == path)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def tree_page(
        self,
        space_id: uuid.UUID,
        *,
        drafts: bool,
        after: tuple[str, uuid.UUID] | None,
        limit: int,
        among: Select[uuid.UUID] | None = None,
    ) -> list[Page]:
        """The space's pages outside the trash, by path: parents before children;
        with `among`, only the pages whose ids it selects."""
        stmt = (
            select(Page)
            .where(self._live(), Page.space_id == space_id)
            .order_by(Page.path, Page.id)
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        if not drafts:
            stmt = stmt.where(Page.status == PageStatus.PUBLISHED)
        if after is not None:
            stmt = stmt.where(tuple_(Page.path, Page.id) > tuple_(*after))
        if among is not None:
            stmt = stmt.where(Page.id.in_(among))
        return list((await self.session.scalars(stmt)).all())

    async def sibling_slugs(self, space_id: uuid.UUID, parent_id: uuid.UUID | None) -> set[str]:
        stmt = select(Page.slug).where(self._live(), Page.space_id == space_id, under(parent_id))
        return set((await self.session.scalars(stmt)).all())

    async def children(self, space_id: uuid.UUID, parent_id: uuid.UUID | None) -> list[Page]:
        """Siblings outside the trash, in their order."""
        stmt = (
            select(Page)
            .where(self._live(), Page.space_id == space_id, under(parent_id))
            .order_by(Page.sort_order, Page.id)
            .execution_options(populate_existing=True)
        )
        return list((await self.session.scalars(stmt)).all())

    async def next_sort_order(self, space_id: uuid.UUID, parent_id: uuid.UUID | None) -> int:
        stmt = select(func.max(Page.sort_order)).where(
            self._live(), Page.space_id == space_id, under(parent_id)
        )
        current = await self.session.scalar(stmt)
        return 0 if current is None else int(current) + 1

    async def titles(
        self, ids: Iterable[uuid.UUID], drafts: Select[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """The titles of those pages the actor sees (`page_seen`), by id."""
        wanted = list(set(ids))
        if not wanted:
            return {}
        seen = page_seen(self.scope.org_id, self.scope.space_ids, drafts)
        stmt = select(Page.id, Page.title).where(seen, Page.id.in_(wanted))
        return {row.id: row.title for row in await self.session.execute(stmt)}
