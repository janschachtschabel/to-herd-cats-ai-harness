"""The SQL of wiki pages. Every statement is scoped by the actor's organisation and the
spaces it may read (`PageScope`, built from `access.visible_space_ids`), so a page in a
space the actor cannot see is never even loaded."""

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, and_, func, select, tuple_
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

    async def live(self, page_id: uuid.UUID, *, lock: bool = False) -> Page | None:
        """A page outside the trash; with `lock`, the row as committed now, locked
        until the transaction ends."""
        stmt = select(Page).where(self._live(), Page.id == page_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def live_in_space(self, space_id: uuid.UUID, page_id: uuid.UUID) -> Page | None:
        stmt = (
            select(Page)
            .where(self._live(), Page.space_id == space_id, Page.id == page_id)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def by_path(self, space_id: uuid.UUID, path: str) -> Page | None:
        stmt = select(Page).where(self._live(), Page.space_id == space_id, Page.path == path)
        return await self.session.scalar(stmt)

    async def tree_page(
        self,
        space_id: uuid.UUID,
        *,
        drafts: bool,
        after: tuple[str, uuid.UUID] | None,
        limit: int,
    ) -> list[Page]:
        """The space's pages outside the trash, by path: parents before children."""
        stmt = (
            select(Page)
            .where(self._live(), Page.space_id == space_id)
            .order_by(Page.path, Page.id)
            .limit(limit)
        )
        if not drafts:
            stmt = stmt.where(Page.status == PageStatus.PUBLISHED)
        if after is not None:
            stmt = stmt.where(tuple_(Page.path, Page.id) > tuple_(*after))
        return list((await self.session.scalars(stmt)).all())

    async def sibling_slugs(self, space_id: uuid.UUID, parent_id: uuid.UUID | None) -> set[str]:
        stmt = select(Page.slug).where(self._live(), Page.space_id == space_id, under(parent_id))
        return set((await self.session.scalars(stmt)).all())

    async def next_sort_order(self, space_id: uuid.UUID, parent_id: uuid.UUID | None) -> int:
        stmt = select(func.max(Page.sort_order)).where(
            self._live(), Page.space_id == space_id, under(parent_id)
        )
        current = await self.session.scalar(stmt)
        return 0 if current is None else int(current) + 1
