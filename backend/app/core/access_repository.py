"""The SQL of the permission check: what is known about an actor and a space, in one
statement, and the filter of the spaces an actor may read.

Both are built from the same pieces (`_subject_role`, `_in_scope`, `held_by`), so the
single check and the list filter cannot drift apart. A later `read_scope` on the actor
(spec 5.6) narrows `_in_scope` and with it both.
"""

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import (
    ColumnElement,
    ScalarSelect,
    Select,
    SQLColumnExpression,
    and_,
    case,
    exists,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.permissions import ADMIN_ROLES, OPEN_SPACE_READERS, SpaceRole
from app.core.principal import PrincipalType, SystemRole
from app.modules.groups.models import GroupMember
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


_REMEMBERED = "herd.access_facts"


@contextmanager
def remembered_facts(session: AsyncSession) -> Iterator[None]:
    """Within: each actor's facts per space are read once and then reused. For one
    operation that checks the same rights many times in its own transaction (an
    import of thousands of pages, review M2 R19); its rights are those it started with."""
    session.info[_REMEMBERED] = {}
    try:
        yield
    finally:
        session.info.pop(_REMEMBERED, None)


def first_time(session: AsyncSession, key: object) -> bool:
    """False if `key` was already seen within `remembered_facts` (always True outside):
    an admin's access to a space is recorded once per such operation, not per check."""
    remembered: dict[object, object] | None = session.info.get(_REMEMBERED)
    if remembered is None:
        return True
    seen = ("first_time", key)
    if seen in remembered:
        return False
    remembered[seen] = True
    return True


class AccessRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def facts(self, actor: Actor, space_id: uuid.UUID | None) -> AccessFacts:
        """Everything a check needs, in one query (or remembered, see above)."""
        remembered: dict[object, object] | None = self.session.info.get(_REMEMBERED)
        if remembered is None:
            return await self._facts(actor, space_id)
        key = (actor.org_id, actor.principal, actor.group_ids, space_id)
        facts = remembered.get(key)
        if not isinstance(facts, AccessFacts):
            facts = remembered[key] = await self._facts(actor, space_id)
        return facts

    async def _facts(self, actor: Actor, space_id: uuid.UUID | None) -> AccessFacts:
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


@lru_cache(maxsize=1024)
def visible_ids_stmt(actor: Actor) -> Select[uuid.UUID]:
    """Ids of the spaces `actor` may read: all of the organisation's for admins;
    otherwise those the actor or one of its groups is a member of, plus the open ones
    for roles that read open spaces. Nothing once the actor no longer acts.

    The statement depends on nothing but the actor (it is evaluated when it runs), and
    SQL constructs are immutable, so it is built once per actor (review M2 R19)."""
    role = _subject_role(actor)
    member = exists().where(SpaceMember.space_id == Space.id, held_by(actor.principals))
    open_to_role = and_(Space.kind == SpaceKind.OPEN, role.in_(OPEN_SPACE_READERS))
    return select(Space.id).where(
        _in_scope(actor),
        role.is_not(None),
        or_(role.in_(ADMIN_ROLES), member, open_to_role),
    )


def _person_member(min_role: SpaceRole | None = None) -> ColumnElement[bool]:
    """The (correlated) `User`, or one of its groups as they are now, is a member of the
    (correlated) `Space`, with at least `min_role` if given."""
    # Every table but the subquery's own is the caller's (correlated), however deep.
    groups = (
        select(GroupMember.group_id)
        .where(GroupMember.member_type == PrincipalType.USER, GroupMember.member_id == User.id)
        .correlate_except(GroupMember)
    )
    clauses = [
        SpaceMember.space_id == Space.id,
        or_(
            and_(SpaceMember.member_type == PrincipalType.USER, SpaceMember.member_id == User.id),
            and_(SpaceMember.member_type == PrincipalType.GROUP, SpaceMember.member_id.in_(groups)),
        ),
    ]
    if min_role is not None:
        clauses.append(_RANK >= min_role.rank)
    return exists().where(*clauses).correlate_except(SpaceMember)


def person_reads_space(space_id: SQLColumnExpression[uuid.UUID | None]) -> ColumnElement[bool]:
    """The rule of `visible_ids_stmt` seen from the other side: whether the (correlated)
    `User` row may read the space `space_id`, with the person's groups as they are now.
    For questions about many people at once ("who of these may see it?", review M3
    focus 4 and 5) in one statement; `tests/test_conversation_readers.py` holds both
    forms to the same answers."""
    open_to_role = and_(Space.kind == SpaceKind.OPEN, User.system_role.in_(OPEN_SPACE_READERS))
    readable = (
        exists()
        .where(
            Space.id == space_id,
            Space.org_id == User.org_id,
            or_(User.system_role.in_(ADMIN_ROLES), _person_member(), open_to_role),
        )
        .correlate_except(Space)
    )
    return and_(User.is_active.is_(True), readable)


def person_holds_role(
    space_id: SQLColumnExpression[uuid.UUID | None], min_role: SpaceRole
) -> ColumnElement[bool]:
    """`ids_with_role_stmt` seen from the other side: whether the (correlated) `User`
    holds at least `min_role` in the space (admins hold every role; the open-space
    floor gives no more than `viewer`)."""
    if min_role == SpaceRole.VIEWER:
        return person_reads_space(space_id)
    held = (
        exists()
        .where(
            Space.id == space_id,
            Space.org_id == User.org_id,
            or_(User.system_role.in_(ADMIN_ROLES), _person_member(min_role)),
        )
        .correlate_except(Space)
    )
    return and_(User.is_active.is_(True), held)


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
