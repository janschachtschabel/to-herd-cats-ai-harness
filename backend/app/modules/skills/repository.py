"""The SQL of skills and their versions. Every statement starts from the organisation;
what an actor sees is one rule, `visible`: organisation-wide skills, and those of the
spaces in `space_ids` (the spaces the actor may read)."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, and_, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal, PrincipalType
from app.core.repository import advisory_xact_lock
from app.modules.agents.models import Agent
from app.modules.skills.models import Skill, SkillState, SkillVersion
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class SkillScope:
    org_id: uuid.UUID
    space_ids: Select[uuid.UUID]  # the spaces whose skills the actor may read


@dataclass(frozen=True, slots=True)
class SkillFilter:
    space_id: uuid.UUID | None = None
    org_wide: bool | None = None  # True: only organisation-wide; False: only of spaces
    state: SkillState | None = None
    query: str | None = None  # a part of the name


def visible(scope: SkillScope) -> ColumnElement[bool]:
    return and_(
        Skill.org_id == scope.org_id,
        or_(Skill.space_id.is_(None), Skill.space_id.in_(scope.space_ids)),
    )


class SkillRepository:
    def __init__(self, session: AsyncSession, scope: SkillScope) -> None:
        self.session = session
        self.scope = scope

    async def add(self, skill: Skill) -> Skill:
        self.session.add(skill)
        await self.session.flush()
        return skill

    async def get(self, skill_id: uuid.UUID, *, lock: bool = False) -> Skill | None:
        """A skill the scope sees; with `lock`, as committed now and locked until the
        transaction ends (a write waits for the one before)."""
        stmt = (
            select(Skill)
            .where(visible(self.scope), Skill.id == skill_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def page(
        self, where: SkillFilter, after: tuple[str, uuid.UUID] | None, limit: int
    ) -> list[Skill]:
        """By name, then id."""
        stmt = select(Skill).where(visible(self.scope))
        if where.space_id is not None:
            stmt = stmt.where(Skill.space_id == where.space_id)
        if where.org_wide is True:
            stmt = stmt.where(Skill.space_id.is_(None))
        elif where.org_wide is False:
            stmt = stmt.where(Skill.space_id.is_not(None))
        if where.state is not None:
            stmt = stmt.where(Skill.state == where.state)
        if where.query:
            stmt = stmt.where(Skill.name.icontains(where.query, autoescape=True))
        if after is not None:
            stmt = stmt.where(tuple_(Skill.name, Skill.id) > tuple_(*after))
        stmt = stmt.order_by(Skill.name, Skill.id).limit(limit)
        return list(await self.session.scalars(stmt))

    async def lock_names(self) -> None:
        await advisory_xact_lock(self.session, f"skills.names:{self.scope.org_id}")

    async def name_taken(
        self, space_id: uuid.UUID | None, name: str, besides: uuid.UUID | None = None
    ) -> bool:
        """Any skill of the scope, seen by the actor or not (names are unique)."""
        same_scope = Skill.space_id.is_(None) if space_id is None else Skill.space_id == space_id
        stmt = select(Skill.id).where(Skill.org_id == self.scope.org_id, same_scope)
        stmt = stmt.where(Skill.name == name)
        if besides is not None:
            stmt = stmt.where(Skill.id != besides)
        return await self.session.scalar(stmt.limit(1)) is not None

    # --- versions ------------------------------------------------------------------

    async def add_version(self, skill: Skill, author: Principal) -> SkillVersion:
        """The skill's current description and content as its next version."""
        number = await self.session.scalar(
            select(func.coalesce(func.max(SkillVersion.number), 0) + 1).where(
                SkillVersion.org_id == self.scope.org_id, SkillVersion.skill_id == skill.id
            )
        )
        version = SkillVersion(
            org_id=self.scope.org_id,
            skill_id=skill.id,
            number=int(number or 1),
            description=skill.description,
            content=skill.content,
            author_type=author.type,
            author_id=author.id,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def versions(
        self, skill_id: uuid.UUID, before: uuid.UUID | None, limit: int
    ) -> list[SkillVersion]:
        """Newest first (ids grow with the numbers)."""
        stmt = select(SkillVersion).where(
            SkillVersion.org_id == self.scope.org_id, SkillVersion.skill_id == skill_id
        )
        if before is not None:
            stmt = stmt.where(SkillVersion.id < before)
        stmt = stmt.order_by(SkillVersion.id.desc()).limit(limit)
        return list(await self.session.scalars(stmt))

    async def version(self, skill_id: uuid.UUID, number: int) -> SkillVersion | None:
        return await self.session.scalar(
            select(SkillVersion).where(
                SkillVersion.org_id == self.scope.org_id,
                SkillVersion.skill_id == skill_id,
                SkillVersion.number == number,
            )
        )

    # --- for showing -----------------------------------------------------------------

    async def names(self, principals: Collection[Principal]) -> dict[Principal, str]:
        """Display names of people and agents of the organisation."""
        users = {p.id for p in principals if p.type == PrincipalType.USER}
        agents = {p.id for p in principals if p.type == PrincipalType.AGENT}
        found: dict[Principal, str] = {}
        if users:
            rows = await self.session.execute(
                select(User.id, User.name).where(
                    User.org_id == self.scope.org_id, User.id.in_(users)
                )
            )
            found |= {Principal.user(i): n for i, n in rows}
        if agents:
            rows = await self.session.execute(
                select(Agent.id, Agent.name).where(
                    Agent.org_id == self.scope.org_id, Agent.id.in_(agents)
                )
            )
            found |= {Principal.agent(i): n for i, n in rows}
        return found
