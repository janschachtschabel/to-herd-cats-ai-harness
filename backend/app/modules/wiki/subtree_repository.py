"""SQL over whole subtrees: moving paths, the trash, restoring, purging. Scoped like
`PageRepository`. Bulk statements leave rows already in the session as they were;
the repositories' reads refresh them.

A page in the trash keeps its path and parent. Pages trashed together share one
`trashed_at`, so a batch is found again by following parent links from its root
through pages with the same time.
"""

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, Select, delete, exists, func, or_, select, tuple_, update
from sqlalchemy.orm import aliased

from app.modules.wiki.models import Page, PageStatus
from app.modules.wiki.repository import PageRepository

_SEGMENTS = func.length(Page.path) - func.length(func.replace(Page.path, "/", "")) + 1


def _at_or_below(path: str) -> ColumnElement[bool]:
    return or_(Page.path == path, func.starts_with(Page.path, f"{path}/"))


class SubtreeRepository(PageRepository):
    async def deepest_at_or_below(self, space_id: uuid.UUID, path: str) -> int:
        """The most path segments among the live page at `path` and its descendants."""
        stmt = select(func.max(_SEGMENTS)).where(
            self._live(), Page.space_id == space_id, _at_or_below(path)
        )
        return int(await self.session.scalar(stmt) or 0)

    async def published_at_or_below(self, space_id: uuid.UUID, path: str) -> bool:
        """Whether the live page at `path` or a live descendant is published."""
        stmt = select(
            exists().where(
                self._live(),
                Page.space_id == space_id,
                Page.status == PageStatus.PUBLISHED,
                _at_or_below(path),
            )
        )
        return bool(await self.session.scalar(stmt))

    async def rewrite_descendant_paths(self, space_id: uuid.UUID, old: str, new: str) -> None:
        """Live pages below `old` move below `new`."""
        stmt = (
            update(Page)
            .where(self._live(), Page.space_id == space_id, func.starts_with(Page.path, f"{old}/"))
            .values(path=func.concat(new, func.substr(Page.path, len(old) + 1)))
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(stmt)

    async def trash_at_or_below(self, space_id: uuid.UUID, path: str, at: datetime) -> int:
        """Put the live page at `path` and every live descendant into the trash at
        `at`; their live sessions end. Returns how many pages that was."""
        stmt = (
            update(Page)
            .where(self._live(), Page.space_id == space_id, _at_or_below(path))
            .values(
                trashed_at=at,
                version=Page.version + 1,
                collab_generation=Page.collab_generation + 1,
            )
            .returning(Page.id)
            .execution_options(synchronize_session=False)
        )
        return len((await self.session.execute(stmt)).all())

    async def trashed(self, page_id: uuid.UUID) -> Page | None:
        stmt = (
            select(Page)
            .where(self._scoped(), Page.id == page_id, Page.trashed_at.is_not(None))
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def trashed_with(self, root: Page) -> list[Page]:
        """The pages below `root` that went into the trash together with it."""
        stmt = (
            select(Page)
            .where(self._scoped(), Page.id.in_(_descendant_ids(root.id, root.trashed_at)))
            .execution_options(populate_existing=True)
        )
        return list((await self.session.scalars(stmt)).all())

    async def restore_below(self, ids: list[uuid.UUID], old: str, new: str) -> None:
        """Bring the pages `ids` (below a restored page) back, from below `old` to
        below `new`; their live sessions end."""
        if not ids:
            return
        stmt = (
            update(Page)
            .where(self._scoped(), Page.id.in_(ids))
            .values(
                path=func.concat(new, func.substr(Page.path, len(old) + 1)),
                trashed_at=None,
                version=Page.version + 1,
                collab_generation=Page.collab_generation + 1,
            )
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(stmt)

    async def trash_roots(
        self, space_id: uuid.UUID, before: tuple[datetime, uuid.UUID] | None, limit: int
    ) -> list[Page]:
        """The pages that went into the trash on their own or as the top of a batch,
        newest first."""
        parent = aliased(Page)
        stmt = (
            select(Page)
            .outerjoin(parent, parent.id == Page.parent_id)
            .where(
                self._scoped(),
                Page.space_id == space_id,
                Page.trashed_at.is_not(None),
                or_(parent.id.is_(None), parent.trashed_at.is_distinct_from(Page.trashed_at)),
            )
            .order_by(Page.trashed_at.desc(), Page.id.desc())
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        if before is not None:
            stmt = stmt.where(tuple_(Page.trashed_at, Page.id) < tuple_(*before))
        return list((await self.session.scalars(stmt)).all())

    async def ids_at_or_below(self, root_id: uuid.UUID) -> list[uuid.UUID]:
        """The page and every page below it by parent links, in the trash or not."""
        stmt = select(Page.id).where(
            self._scoped(),
            or_(Page.id == root_id, Page.id.in_(_descendant_ids(root_id, None))),
        )
        return list((await self.session.scalars(stmt)).all())

    async def delete_subtree(self, root_id: uuid.UUID) -> list[uuid.UUID]:
        """Delete the page and everything below it, for good; returns their ids."""
        stmt = (
            delete(Page)
            .where(
                self._scoped(),
                or_(Page.id == root_id, Page.id.in_(_descendant_ids(root_id, None))),
            )
            .returning(Page.id)
            .execution_options(synchronize_session=False)
        )
        return list((await self.session.scalars(stmt)).all())


def _descendant_ids(root_id: uuid.UUID, trashed_at: datetime | None) -> Select[tuple[uuid.UUID]]:
    """Ids below `root_id` by parent links; with `trashed_at`, only through pages
    trashed at that time."""
    child = aliased(Page)
    tree = select(Page.id).where(Page.parent_id == root_id)
    if trashed_at is not None:
        tree = tree.where(Page.trashed_at == trashed_at)
    cte = tree.cte("below", recursive=True)
    step = select(child.id).join(cte, child.parent_id == cte.c.id)
    if trashed_at is not None:
        step = step.where(child.trashed_at == trashed_at)
    cte = cte.union_all(step)
    return select(cte.c.id)
