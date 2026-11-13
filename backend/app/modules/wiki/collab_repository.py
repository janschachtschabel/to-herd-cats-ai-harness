"""The SQL of live editing: the page row (in or out of the trash, so an ended session
is told so) and its live state, scoped by the editors' organisation. Who may see and
edit the page is the service's check, per editor.

`page_by_id` is the one unscoped read: the internal API is trusted, and a check that
must end a generation takes the organisation from the page row when no session that
joined is valid any more."""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.wiki.collab_models import PageCollabState
from app.modules.wiki.models import Page


async def page_by_id(
    session: AsyncSession, page_id: uuid.UUID, *, lock: bool = False
) -> Page | None:
    """The page row by id alone (in or out of the trash); only for the trusted
    internal API, which then scopes everything else by `page.org_id`."""
    stmt = select(Page).where(Page.id == page_id).execution_options(populate_existing=True)
    if lock:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


class CollabRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def page(self, page_id: uuid.UUID, *, lock: bool = False) -> Page | None:
        stmt = (
            select(Page)
            .where(Page.org_id == self.org_id, Page.id == page_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def state(self, page_id: uuid.UUID) -> PageCollabState | None:
        stmt = select(PageCollabState).where(
            PageCollabState.org_id == self.org_id, PageCollabState.page_id == page_id
        )
        return await self.session.scalar(stmt)

    async def put_state(self, page_id: uuid.UUID, generation: int, ydoc: bytes) -> None:
        """Replace the page's live state (the caller holds the page row lock)."""
        now = utcnow()
        stmt = insert(PageCollabState).values(
            page_id=page_id, org_id=self.org_id, generation=generation, ydoc=ydoc, updated_at=now
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[PageCollabState.page_id],
            set_={"generation": generation, "ydoc": ydoc, "updated_at": now},
            where=PageCollabState.org_id == self.org_id,
        )
        await self.session.execute(stmt)
