"""The SQL of page versions, scoped like the pages: the actor's organisation and
versions of pages in spaces it may read."""

import uuid
from typing import NamedTuple

from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import PrincipalType
from app.modules.users.models import User
from app.modules.wiki.models import Page, PageVersion
from app.modules.wiki.repository import PageScope


class NamedVersion(NamedTuple):
    """A version with its author's display name (None if the author is no person)."""

    version: PageVersion
    author_name: str | None


def _author_name() -> ColumnElement[str | None]:
    return (
        select(User.name)
        .where(PageVersion.author_type == PrincipalType.USER, User.id == PageVersion.author_id)
        .scalar_subquery()
    )


class VersionRepository:
    def __init__(self, session: AsyncSession, scope: PageScope) -> None:
        self.session = session
        self.scope = scope

    def _scoped(self) -> ColumnElement[bool]:
        pages = select(Page.id).where(
            Page.org_id == self.scope.org_id, Page.space_id.in_(self.scope.space_ids)
        )
        return and_(PageVersion.org_id == self.scope.org_id, PageVersion.page_id.in_(pages))

    async def add(self, version: PageVersion) -> PageVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def latest(self, page_id: uuid.UUID) -> PageVersion | None:
        """The page's newest version, locked until the transaction ends."""
        stmt = (
            select(PageVersion)
            .where(self._scoped(), PageVersion.page_id == page_id)
            .order_by(PageVersion.number.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def get(self, page_id: uuid.UUID, number: int) -> NamedVersion | None:
        stmt = (
            select(PageVersion, _author_name())
            .where(self._scoped(), PageVersion.page_id == page_id, PageVersion.number == number)
            .execution_options(populate_existing=True)
        )
        row = (await self.session.execute(stmt)).first()
        return NamedVersion(row[0], row[1]) if row else None

    async def page(
        self, page_id: uuid.UUID, before: uuid.UUID | None, limit: int
    ) -> list[NamedVersion]:
        """Newest first; `before` is the id of the last version seen."""
        stmt = (
            select(PageVersion, _author_name())
            .where(self._scoped(), PageVersion.page_id == page_id)
            .order_by(PageVersion.number.desc())
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        if before is not None:
            seen = select(PageVersion.number).where(
                PageVersion.page_id == page_id, PageVersion.id == before
            )
            stmt = stmt.where(PageVersion.number < seen.scalar_subquery())
        return [NamedVersion(v, n) for v, n in (await self.session.execute(stmt)).all()]
