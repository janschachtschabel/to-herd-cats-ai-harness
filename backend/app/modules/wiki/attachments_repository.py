"""The SQL of attachments, scoped like pages: the actor's organisation and the spaces
it may read (`PageScope`). Whether the page itself is visible (drafts, the trash) is
the service's check."""

import uuid

from sqlalchemy import ColumnElement, and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import advisory_xact_lock
from app.modules.wiki.models import Attachment
from app.modules.wiki.repository import PageScope


class AttachmentRepository:
    def __init__(self, session: AsyncSession, scope: PageScope) -> None:
        self.session = session
        self.scope = scope

    def _scoped(self) -> ColumnElement[bool]:
        return and_(
            Attachment.org_id == self.scope.org_id,
            Attachment.space_id.in_(self.scope.space_ids),
        )

    async def lock_blob(self, sha256: str) -> None:
        """Serialise writing, counting and deleting the file of one content."""
        await advisory_xact_lock(self.session, f"attachment.blob:{self.scope.org_id}:{sha256}")

    async def add(self, attachment: Attachment) -> Attachment:
        self.session.add(attachment)
        await self.session.flush()
        return attachment

    async def get(self, attachment_id: uuid.UUID) -> Attachment | None:
        stmt = select(Attachment).where(self._scoped(), Attachment.id == attachment_id)
        return await self.session.scalar(stmt)

    async def page(
        self, page_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[Attachment]:
        """Oldest first."""
        stmt = (
            select(Attachment)
            .where(self._scoped(), Attachment.page_id == page_id)
            .order_by(Attachment.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(Attachment.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def of_pages(self, page_ids: list[uuid.UUID]) -> list[Attachment]:
        stmt = (
            select(Attachment)
            .where(self._scoped(), Attachment.page_id.in_(page_ids))
            .order_by(Attachment.id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def delete(self, attachment: Attachment) -> None:
        await self.session.delete(attachment)
        await self.session.flush()

    async def delete_of_pages(self, page_ids: list[uuid.UUID]) -> list[Attachment]:
        """Delete the attachments of the pages; returns them (for their files)."""
        if not page_ids:
            return []
        stmt = (
            delete(Attachment)
            .where(self._scoped(), Attachment.page_id.in_(page_ids))
            .returning(Attachment)
            .execution_options(synchronize_session=False)
        )
        return list((await self.session.scalars(stmt)).all())

    async def uses_blob(self, sha256: str) -> bool:
        """Whether any attachment of the organisation still has this content; looks
        past the actor's view, since the file is shared organisation-wide."""
        stmt = select(func.count()).where(
            Attachment.org_id == self.scope.org_id, Attachment.sha256 == sha256
        )
        return bool(await self.session.scalar(stmt))
