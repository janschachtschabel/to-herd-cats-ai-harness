import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orgs.models import Organization


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_default(self) -> Organization | None:
        """The installation's organisation: the first one created (ids are UUIDv7)."""
        stmt = select(Organization).order_by(Organization.id).limit(1)
        return await self.session.scalar(stmt)

    async def get(self, org_id: uuid.UUID) -> Organization:
        """An organisation that must exist (a person's or a session's: foreign keys)."""
        return await self.session.get_one(Organization, org_id)

    async def add(self, org: Organization) -> Organization:
        self.session.add(org)
        await self.session.flush()
        return org
