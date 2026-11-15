import uuid
from collections.abc import Collection

from sqlalchemy import func, select

from app.core.principal import SystemRole
from app.core.repository import BaseRepository, advisory_xact_lock
from app.modules.users.models import User


class UserRepository(BaseRepository[User]):
    model = User

    async def lock_admin_writes(self, org_id: uuid.UUID) -> None:
        """Serialise changes to an organisation's people, so the version check, the email
        check and the last-owner count each see the effect of the write before them."""
        await advisory_xact_lock(self.session, f"users:{org_id}")

    async def get_current(self, org_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        """The row as committed now, even if this session loaded it earlier."""
        stmt = (
            select(User)
            .where(User.org_id == org_id, User.id == user_id)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def get_by_email(self, org_id: uuid.UUID, email: str) -> User | None:
        stmt = select(User).where(User.org_id == org_id, User.email == email.lower())
        return await self.session.scalar(stmt)

    async def page(
        self, org_id: uuid.UUID, after: uuid.UUID | None, limit: int, *, pending: bool = False
    ) -> list[User]:
        """The organisation's people by id; `pending`: only those awaiting approval."""
        stmt = select(User).where(User.org_id == org_id).order_by(User.id).limit(limit)
        if pending:
            stmt = stmt.where(User.awaiting_approval_since.is_not(None))
        if after is not None:
            stmt = stmt.where(User.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def count_pending(self, org_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(
            User.org_id == org_id, User.awaiting_approval_since.is_not(None)
        )
        return int(await self.session.scalar(stmt) or 0)

    async def names(
        self, org_id: uuid.UUID, user_ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """The names of these people of the organisation (deactivated ones too)."""
        if not user_ids:
            return {}
        stmt = select(User.id, User.name).where(User.org_id == org_id, User.id.in_(user_ids))
        return {user_id: name for user_id, name in await self.session.execute(stmt)}

    async def active_ids(self, org_id: uuid.UUID) -> list[uuid.UUID]:
        """Every active person of the organisation (for announcements to all)."""
        stmt = select(User.id).where(User.org_id == org_id, User.is_active.is_(True))
        return list(await self.session.scalars(stmt.order_by(User.id)))

    async def active_ids_with_roles(
        self, org_id: uuid.UUID, roles: Collection[SystemRole]
    ) -> list[uuid.UUID]:
        """The active people of the organisation holding one of these system roles."""
        stmt = select(User.id).where(
            User.org_id == org_id,
            User.is_active.is_(True),
            User.system_role.in_([r.value for r in roles]),
        )
        return list(await self.session.scalars(stmt.order_by(User.id)))

    async def exists_any(self) -> bool:
        return bool(await self.session.scalar(select(select(User.id).exists())))

    async def count_active_owners(self, org_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(User)
            .where(
                User.org_id == org_id,
                User.system_role == SystemRole.OWNER,
                User.is_active.is_(True),
            )
        )
        return int(await self.session.scalar(stmt) or 0)
