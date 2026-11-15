"""SQL for access tokens. Everything is scoped by the organisation except `lookup`,
which finds a token by its hash before anyone's organisation is known; what it finds
carries its organisation, and everything after it is scoped by that."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, and_, false, func, not_, or_, select, true, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.ai.models import DataLocation, UserAssignment
from app.modules.ai.policy_filters import ai_space_ids
from app.modules.spaces.models import Space, SpaceKind
from app.modules.tokens.models import AccessToken, McpSetting
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class McpStanding:
    """What decides a person's `mcp.use` (`standing.may_use_mcp`): whether they are
    active, their system role, the organisation's switch, and whether their own AI
    assignment expressly keeps them from AI (`no_ai`)."""

    is_active: bool
    system_role: SystemRole
    enabled: bool
    kept_from_ai: bool


@dataclass(frozen=True, slots=True)
class Found:
    """A token with what decides whether it may act now: its person's standing and the
    organisation's MCP settings, all from the one statement."""

    token: AccessToken
    standing: McpStanding
    location: DataLocation

    @property
    def system_role(self) -> SystemRole:
        return self.standing.system_role


@dataclass(frozen=True, slots=True)
class Listed:
    token: AccessToken
    user_name: str


class TokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lookup(self, digest: bytes) -> Found | None:
        stmt = (
            select(
                AccessToken,
                User.is_active,
                User.system_role,
                func.coalesce(McpSetting.enabled, false()),
                _kept_from_ai(),
                func.coalesce(McpSetting.data_location, DataLocation.EXTERNAL.value),
            )
            .join(User, and_(User.id == AccessToken.user_id, User.org_id == AccessToken.org_id))
            .outerjoin(McpSetting, McpSetting.org_id == AccessToken.org_id)
            .outerjoin(UserAssignment, _own_assignment())
            .where(AccessToken.token_hash == digest)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            return None
        token, active, role, enabled, kept, location = row
        standing = McpStanding(bool(active), SystemRole(role), bool(enabled), bool(kept))
        return Found(token, standing, DataLocation(location))

    async def touch(self, org_id: uuid.UUID, token_id: uuid.UUID, minute: datetime) -> None:
        """`last_used_at` to `minute`, unless it is there already (or later)."""
        await self.session.execute(
            update(AccessToken)
            .where(
                AccessToken.org_id == org_id,
                AccessToken.id == token_id,
                or_(AccessToken.last_used_at.is_(None), AccessToken.last_used_at < minute),
            )
            .values(last_used_at=minute)
        )

    async def scope_spaces(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        space_ids: list[uuid.UUID] | None,
        location: DataLocation,
    ) -> list[uuid.UUID]:
        """The spaces a token's scope names (None: all of the organisation's but other
        people's personal spaces) whose AI policy lets `location` receive them; the
        person's rights are applied by the check, not here."""
        listed = Space.id.in_(space_ids) if space_ids is not None else true()
        others_personal = and_(Space.kind == SpaceKind.PERSONAL, Space.owner_user_id != user_id)
        stmt = select(Space.id).where(
            Space.org_id == org_id,
            Space.id.in_(ai_space_ids(org_id, location)),
            listed,
            not_(others_personal),
        )
        return list((await self.session.scalars(stmt)).all())

    async def add(self, token: AccessToken) -> AccessToken:
        self.session.add(token)
        await self.session.flush()
        return token

    async def get(
        self, org_id: uuid.UUID, token_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> AccessToken | None:
        stmt = select(AccessToken).where(AccessToken.org_id == org_id, AccessToken.id == token_id)
        if user_id is not None:
            stmt = stmt.where(AccessToken.user_id == user_id)
        return await self.session.scalar(stmt)

    async def revoke(self, org_id: uuid.UUID, token_id: uuid.UUID, now: datetime) -> bool:
        """Revoke it unless it was revoked before: whether this call did."""
        stmt = (
            update(AccessToken)
            .where(
                AccessToken.org_id == org_id,
                AccessToken.id == token_id,
                AccessToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
            .returning(AccessToken.id)
        )
        return (await self.session.scalar(stmt)) is not None

    async def own_page(
        self, org_id: uuid.UUID, user_id: uuid.UUID, before: uuid.UUID | None, limit: int
    ) -> list[AccessToken]:
        """The person's tokens, newest first."""
        stmt = select(AccessToken).where(
            AccessToken.org_id == org_id, AccessToken.user_id == user_id
        )
        if before is not None:
            stmt = stmt.where(AccessToken.id < before)
        stmt = stmt.order_by(AccessToken.id.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def all_page(
        self, org_id: uuid.UUID, before: uuid.UUID | None, limit: int
    ) -> list[Listed]:
        """Every token of the organisation with its person's name, newest first."""
        stmt = (
            select(AccessToken, User.name)
            .join(User, User.id == AccessToken.user_id)
            .where(AccessToken.org_id == org_id, User.org_id == org_id)
        )
        if before is not None:
            stmt = stmt.where(AccessToken.id < before)
        stmt = stmt.order_by(AccessToken.id.desc()).limit(limit)
        return [Listed(token, name) for token, name in (await self.session.execute(stmt)).all()]


class McpSettingRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def get(self) -> McpSetting | None:
        stmt = select(McpSetting).where(McpSetting.org_id == self.org_id)
        return await self.session.scalar(stmt)

    async def standing(self, user_id: uuid.UUID) -> McpStanding | None:
        """The person's activity, role and exclusion from AI and the switch, in one
        statement (None: no such person here)."""
        stmt = (
            select(
                User.is_active,
                User.system_role,
                func.coalesce(McpSetting.enabled, false()),
                _kept_from_ai(),
            )
            .outerjoin(McpSetting, McpSetting.org_id == User.org_id)
            .outerjoin(UserAssignment, _own_assignment())
            .where(User.org_id == self.org_id, User.id == user_id)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return McpStanding(bool(row[0]), SystemRole(row[1]), bool(row[2]), bool(row[3]))

    async def lock(self) -> McpSetting:
        """The row, created at version 1 if missing, locked until the transaction ends."""
        await self.session.execute(
            insert(McpSetting)
            .values(org_id=self.org_id, version=1)
            .on_conflict_do_nothing(index_elements=["org_id"])
        )
        stmt = (
            select(McpSetting)
            .where(McpSetting.org_id == self.org_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).one()


def _own_assignment() -> ColumnElement[bool]:
    """The person's own AI assignment (joined to `User`)."""
    return and_(UserAssignment.org_id == User.org_id, UserAssignment.user_id == User.id)


def _kept_from_ai() -> ColumnElement[bool]:
    """Whether the person's own assignment expressly says no AI (spec 7.2)."""
    return func.coalesce(UserAssignment.no_ai, false())
