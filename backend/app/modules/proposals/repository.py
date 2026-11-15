"""The SQL of page proposals: who sees which (one rule, `visible`), lists, locking,
and what the handlers ask (no actor: the event's organisation).

Who sees a proposal (plan M6 decision 8; the rule of drafts and versions, review M2
R16: a proposal is unpublished content and shows the page's earlier content):
- whoever may edit pages in its space (`page.edit`), unless it is a change to a page
  that is in the trash;
- its author, as long as they may read the space and, for a change, the page is
  published and outside the trash (an author who cannot edit sees no drafts).
Nobody else, and a space one cannot read hides all of them. Every statement starts
from the organisation.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, and_, exists, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_repository import person_holds_role
from app.core.permissions import SpaceRole
from app.core.principal import Principal, PrincipalType
from app.modules.ai.models import AiPolicy
from app.modules.groups.models import GroupMember
from app.modules.proposals.models import PageProposal, ProposalKind, ProposalState
from app.modules.spaces.models import AgentWritePolicy, Space, SpaceMember
from app.modules.users.models import User
from app.modules.wiki.models import Page, PageStatus, PageVersion

MODERATING = (SpaceRole.MODERATOR.value, SpaceRole.ADMIN.value)


@dataclass(frozen=True, slots=True)
class ProposalScope:
    org_id: uuid.UUID
    space_ids: Select[uuid.UUID]  # the spaces the actor may read
    edit_space_ids: Select[uuid.UUID]  # those where it may edit pages
    author: Principal  # whose own proposals it sees as their author


def visible(scope: ProposalScope) -> ColumnElement[bool]:
    def page_where(*rules: ColumnElement[bool]) -> ColumnElement[bool]:
        return (
            exists()
            .where(Page.id == PageProposal.page_id, Page.trashed_at.is_(None), *rules)
            .correlate_except(Page)
        )

    new = PageProposal.kind == ProposalKind.NEW
    editor = and_(PageProposal.space_id.in_(scope.edit_space_ids), or_(new, page_where()))
    author = and_(
        PageProposal.author_type == scope.author.type,
        PageProposal.author_id == scope.author.id,
        or_(new, page_where(Page.status == PageStatus.PUBLISHED)),
    )
    return and_(
        PageProposal.org_id == scope.org_id,
        PageProposal.space_id.in_(scope.space_ids),
        or_(editor, author),
    )


class ProposalRepository:
    def __init__(self, session: AsyncSession, scope: ProposalScope) -> None:
        self.session = session
        self.scope = scope

    async def add(self, proposal: PageProposal) -> PageProposal:
        self.session.add(proposal)
        await self.session.flush()
        return proposal

    async def get(self, proposal_id: uuid.UUID, *, lock: bool = False) -> PageProposal | None:
        """A proposal the scope sees; with `lock`, as committed now and locked until
        the transaction ends (a decision or a withdrawal waits for the one before)."""
        stmt = (
            select(PageProposal)
            .where(visible(self.scope), PageProposal.id == proposal_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update(of=PageProposal)
        return await self.session.scalar(stmt)

    async def page(
        self,
        space_id: uuid.UUID,
        state: ProposalState | None,
        before: uuid.UUID | None,
        limit: int,
    ) -> list[PageProposal]:
        """The space's proposals the scope sees, newest first."""
        stmt = (
            select(PageProposal)
            .where(visible(self.scope), PageProposal.space_id == space_id)
            .order_by(PageProposal.id.desc())
            .limit(limit)
        )
        if state is not None:
            stmt = stmt.where(PageProposal.state == state)
        if before is not None:
            stmt = stmt.where(PageProposal.id < before)
        return list((await self.session.scalars(stmt)).all())


class ProposalFacts:
    """Lookups by id within one organisation, after the caller's check (names, version
    numbers, the space's setting) and for the handlers."""

    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def proposal(self, proposal_id: uuid.UUID) -> PageProposal | None:
        stmt = select(PageProposal).where(
            PageProposal.org_id == self.org_id, PageProposal.id == proposal_id
        )
        return await self.session.scalar(stmt)

    async def write_policy(self, space_id: uuid.UUID) -> AgentWritePolicy | None:
        stmt = select(Space.agent_write_policy).where(
            Space.org_id == self.org_id, Space.id == space_id
        )
        return await self.session.scalar(stmt)

    async def ai_policy(self, space_id: uuid.UUID) -> AiPolicy | None:
        stmt = select(Space.ai_policy).where(Space.org_id == self.org_id, Space.id == space_id)
        return await self.session.scalar(stmt)

    async def version_numbers(self, ids: Collection[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not ids:
            return {}
        stmt = select(PageVersion.id, PageVersion.number).where(
            PageVersion.org_id == self.org_id, PageVersion.id.in_(ids)
        )
        return {row[0]: row[1] for row in await self.session.execute(stmt)}

    async def latest_version(self, page_id: uuid.UUID) -> PageVersion | None:
        """The page's newest version (the caller holds the page row)."""
        stmt = (
            select(PageVersion)
            .where(PageVersion.org_id == self.org_id, PageVersion.page_id == page_id)
            .order_by(PageVersion.number.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def user_names(self, ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not ids:
            return {}
        stmt = select(User.id, User.name).where(User.org_id == self.org_id, User.id.in_(ids))
        return {row[0]: row[1] for row in await self.session.execute(stmt)}

    async def moderators(self, space_id: uuid.UUID) -> list[uuid.UUID]:
        """The active people who moderate the space through a membership of their own
        or of a group (`moderator` or `admin`), and hold `page.moderate` there now.
        System admins without such a membership are left out: they may moderate
        everywhere, and would hear of every proposal in every space."""
        direct = exists().where(
            SpaceMember.space_id == space_id,
            SpaceMember.member_type == PrincipalType.USER,
            SpaceMember.member_id == User.id,
            SpaceMember.role.in_(MODERATING),
        )
        through_group = exists().where(
            SpaceMember.space_id == space_id,
            SpaceMember.member_type == PrincipalType.GROUP,
            SpaceMember.role.in_(MODERATING),
            GroupMember.group_id == SpaceMember.member_id,
            GroupMember.member_type == PrincipalType.USER,
            GroupMember.member_id == User.id,
        )
        stmt = (
            select(User.id)
            .where(
                User.org_id == self.org_id,
                or_(direct, through_group),
                person_holds_role(literal(space_id), SpaceRole.MODERATOR),
            )
            .order_by(User.id)
        )
        return list((await self.session.scalars(stmt)).all())
