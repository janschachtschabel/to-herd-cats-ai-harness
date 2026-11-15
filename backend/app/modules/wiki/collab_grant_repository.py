"""The SQL of collab grants (`collab_grants.py`). Lookups go by the token's hash, the
page and the generation together: a grant is never found for another page or
generation. Reads are scoped by the organisation where it is known (the page's);
the lookup that admits a connection knows only the grant, like a login session's
lookup by its token hash."""

import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wiki.collab_models import CollabGrant


class CollabGrantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, grant: CollabGrant) -> None:
        self.session.add(grant)
        await self.session.flush()

    async def bound(
        self,
        hashes: Collection[str],
        *,
        page_id: uuid.UUID,
        generation: int,
        org_id: uuid.UUID | None = None,
    ) -> dict[str, CollabGrant]:
        """The grants among `hashes` issued for exactly this page and generation,
        expired or not, by hash."""
        if not hashes:
            return {}
        stmt = select(CollabGrant).where(
            CollabGrant.token_hash.in_(list(hashes)),
            CollabGrant.page_id == page_id,
            CollabGrant.generation == generation,
        )
        if org_id is not None:
            stmt = stmt.where(CollabGrant.org_id == org_id)
        rows = await self.session.scalars(stmt)
        return {row.token_hash: row for row in rows}

    async def extend(
        self,
        ids: Collection[uuid.UUID],
        *,
        org_id: uuid.UUID,
        now: datetime,
        until: datetime,
    ) -> None:
        """Push the expiry of these live grants (not expired, session still there)."""
        if not ids:
            return
        await self.session.execute(
            update(CollabGrant)
            .where(
                CollabGrant.org_id == org_id,
                CollabGrant.id.in_(list(ids)),
                CollabGrant.session_id.is_not(None),
                CollabGrant.expires_at > now,
            )
            .values(expires_at=until)
        )

    async def delete_expired(self, org_id: uuid.UUID, before: datetime, limit: int) -> None:
        """Up to `limit` grants of the organisation that expired before `before`."""
        doomed = (
            select(CollabGrant.id)
            .where(CollabGrant.org_id == org_id, CollabGrant.expires_at < before)
            .limit(limit)
            .scalar_subquery()
        )
        await self.session.execute(delete(CollabGrant).where(CollabGrant.id.in_(doomed)))
