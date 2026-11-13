"""The SQL of the permission check: what is known about an actor and a space, in one
statement, and the filter of the spaces an actor may read.

Both are built from the same pieces (`_subject_role`, `_in_scope`, `held_by`), so the
single check and the list filter cannot drift apart. A later `read_scope` on the actor
(spec 5.6) narrows `_in_scope` and with it both.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import ColumnElement, ScalarSelect, Select, and_, case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.permissions import ADMIN_ROLES, OPEN_SPACE_READERS, SpaceRole
from app.core.principal import SystemRole
from app.modules.spaces.models import Space, SpaceKind, SpaceMember
from app.modules.spaces.repository import held_by
from app.modules.users.models import User

_RANK = case({role.value: role.rank for role in SpaceRole}, value=SpaceMember.role)


@dataclass(frozen=True, slots=True)
class AccessFacts:
    """`system_role` is None when the actor no longer acts (deactivated, gone);
    `kind` is None when the space does not exist in the actor's organisation;
    `member_role` is the highest role the actor or one of its groups holds there."""

    system_role: SystemRole | None
    kind: SpaceKind | None = None
    member_role: SpaceRole | None = None
    readable: bool = False


class AccessRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def facts(self, actor: Actor, space_id: uuid.UUID | None) -> AccessFacts:
        """Everything a check needs, in one query."""
        role = _subject_role(actor)
        if space_id is None:
            value = await self.session.scalar(select(role))
            return AccessFacts(SystemRole(value) if value else None)
        kind = select(Space.kind).where(_in_scope(actor), Space.id == space_id).scalar_subquery()
        rank = (
            select(func.max(_RANK))
            .where(SpaceMember.space_id == space_id, held_by(actor.principals))
            .scalar_subquery()
        )
        readable = exists(visible_ids_stmt(actor).where(Space.id == space_id))
        row = (await self.session.execute(select(role, kind, rank, readable))).one()
        return AccessFacts(
            system_role=SystemRole(row[0]) if row[0] else None,
            kind=SpaceKind(row[1]) if row[1] else None,
            member_role=SpaceRole.from_rank(row[2]) if row[2] is not None else None,
            readable=bool(row[3]),
        )

    async def facts_in(
        self, actor: Actor, space_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, AccessFacts]:
        """`facts` for many spaces of the actor's organisation, in one query, without
        `readable` (callers pass spaces they already know to be visible)."""
        rank = (
            select(func.max(_RANK))
            .where(SpaceMember.space_id == Space.id, held_by(actor.principals))
            .correlate(Space)
            .scalar_subquery()
        )
        stmt = select(Space.id, _subject_role(actor), Space.kind, rank).where(
            _in_scope(actor), Space.id.in_(space_ids)
        )
        return {
            row[0]: AccessFacts(
                system_role=SystemRole(row[1]) if row[1] else None,
                kind=SpaceKind(row[2]),
                member_role=SpaceRole.from_rank(row[3]) if row[3] is not None else None,
            )
            for row in await self.session.execute(stmt)
        }


def visible_ids_stmt(actor: Actor) -> Select[uuid.UUID]:
    """Ids of the spaces `actor` may read: all of the organisation's for admins;
    otherwise those the actor or one of its groups is a member of, plus the open ones
    for roles that read open spaces. Nothing once the actor no longer acts."""
    role = _subject_role(actor)
    member = exists().where(SpaceMember.space_id == Space.id, held_by(actor.principals))
    open_to_role = and_(Space.kind == SpaceKind.OPEN, role.in_(OPEN_SPACE_READERS))
    return select(Space.id).where(
        _in_scope(actor),
        role.is_not(None),
        or_(role.in_(ADMIN_ROLES), member, open_to_role),
    )


def ids_with_role_stmt(actor: Actor, min_role: SpaceRole) -> Select[uuid.UUID]:
    """Ids of the spaces where `actor` holds at least `min_role`: all of the
    organisation's for admins; otherwise those where the actor or one of its groups is
    a member with such a role, plus the readable ones when `viewer` is enough (the
    open-space floor gives no more than `viewer`)."""
    if min_role == SpaceRole.VIEWER:
        return visible_ids_stmt(actor)
    role = _subject_role(actor)
    member = exists().where(
        SpaceMember.space_id == Space.id,
        held_by(actor.principals),
        _RANK >= min_role.rank,
    )
    return select(Space.id).where(
        _in_scope(actor), role.is_not(None), or_(role.in_(ADMIN_ROLES), member)
    )


def _subject_role(actor: Actor) -> ScalarSelect[str]:
    """The actor's system role as it is now; NULL if it is inactive or not a person of
    the organisation (M1 knows no other principals that act)."""
    return (
        select(User.system_role)
        .where(
            User.org_id == actor.org_id,
            User.id == actor.principal.id,
            User.is_active.is_(True),
        )
        .scalar_subquery()
    )


def _in_scope(actor: Actor) -> ColumnElement[bool]:
    """The spaces a check considers at all: the actor's organisation."""
    return Space.org_id == actor.org_id
