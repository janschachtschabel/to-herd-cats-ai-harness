"""The SQL of direct messages and of the admin's inspection of them.

`DmRepository` is the actor's view (`ConversationScope`): its own DMs only.
`InspectionRepository` is the one place that reads DMs without being a participant;
only `inspect.InspectService` uses it, after checking `dm.inspect`, and it reads
through an inspection that is the admin's own and has not expired.

A DM's last activity is its newest top-level message (else its creation): as an id
(UUIDv7, so ordered by time) it is the key of the DM lists, newest first.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, ScalarSelect, and_, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute

from app.core.principal import Principal, PrincipalType
from app.modules.messaging.models import (
    Conversation,
    ConversationKind,
    ConversationParticipant,
    DmInspection,
    Message,
)
from app.modules.messaging.repository import ConversationScope, takes_part, visible_conversations
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class Participant:
    id: uuid.UUID
    name: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class ListedDm:
    conversation: Conversation
    activity: uuid.UUID  # the sort key (see the module docstring)
    last_message_at: datetime | None


@dataclass(frozen=True, slots=True)
class InspectionNote:
    at: datetime
    admin_name: str


def _newest[T](column: QueryableAttribute[T]) -> ScalarSelect[T]:
    """`column` of the (correlated) conversation's newest top-level message (there is
    no `max` of uuids in PostgreSQL; the index on (conversation_id, id) serves this)."""
    return (
        select(column)
        .where(Message.conversation_id == Conversation.id, Message.parent_id.is_(None))
        .order_by(Message.id.desc())
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )


def _activity() -> ColumnElement[uuid.UUID]:
    return func.coalesce(_newest(Message.id), Conversation.id)


async def _dm_page(
    session: AsyncSession,
    where: ColumnElement[bool],
    after: tuple[uuid.UUID, uuid.UUID] | None,
    limit: int,
) -> list[ListedDm]:
    activity = _activity()
    stmt = (
        select(Conversation, activity, _newest(Message.created_at))
        .where(where, Conversation.kind == ConversationKind.DM)
        .order_by(activity.desc(), Conversation.id.desc())
        .limit(limit)
    )
    if after is not None:
        stmt = stmt.where(tuple_(activity, Conversation.id) < tuple_(*after))
    rows = await session.execute(stmt)
    return [ListedDm(c, key, at) for c, key, at in rows]


async def participants_of(
    session: AsyncSession, org_id: uuid.UUID, conversation_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[Participant]]:
    """The people of each conversation, by name."""
    if not conversation_ids:
        return {}
    stmt = (
        select(ConversationParticipant.conversation_id, User.id, User.name, User.is_active)
        .join(User, User.id == ConversationParticipant.principal_id)
        .where(
            ConversationParticipant.org_id == org_id,
            ConversationParticipant.conversation_id.in_(conversation_ids),
            ConversationParticipant.principal_type == PrincipalType.USER,
        )
        .order_by(User.name, User.id)
    )
    found: dict[uuid.UUID, list[Participant]] = {id_: [] for id_ in conversation_ids}
    for conversation_id, user_id, name, active in await session.execute(stmt):
        found[conversation_id].append(Participant(user_id, name, active))
    return found


class DmRepository:
    def __init__(self, session: AsyncSession, scope: ConversationScope) -> None:
        self.session = session
        self.scope = scope

    async def active_people(self, user_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        """Those of `user_ids` who are active people of the organisation."""
        stmt = select(User.id).where(
            User.org_id == self.scope.org_id,
            User.id.in_(list(user_ids)),
            User.is_active.is_(True),
        )
        return set(await self.session.scalars(stmt))

    async def insert(self, values: dict[str, Any]) -> Conversation | None:
        """A new DM; None when the organisation has one with the same key (also one
        being created concurrently, which is waited for)."""
        stmt = (
            insert(Conversation)
            .values(org_id=self.scope.org_id, kind=ConversationKind.DM, **values)
            .on_conflict_do_nothing(index_elements=["org_id", "dm_key"])
            .returning(Conversation)
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def by_key(self, dm_key: str) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.org_id == self.scope.org_id, Conversation.dm_key == dm_key
        )
        return await self.session.scalar(stmt)

    async def add_participants(
        self, conversation_id: uuid.UUID, user_ids: Iterable[uuid.UUID]
    ) -> None:
        rows = [
            {
                "org_id": self.scope.org_id,
                "conversation_id": conversation_id,
                "principal_type": PrincipalType.USER,
                "principal_id": user_id,
            }
            for user_id in user_ids
        ]
        await self.session.execute(insert(ConversationParticipant).values(rows))

    async def page(self, after: tuple[uuid.UUID, uuid.UUID] | None, limit: int) -> list[ListedDm]:
        """The actor's DMs, by last activity."""
        return await _dm_page(self.session, visible_conversations(self.scope), after, limit)

    async def participants(
        self, conversation_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[Participant]]:
        return await participants_of(self.session, self.scope.org_id, conversation_ids)

    async def inspections(self, conversation_id: uuid.UUID) -> list[InspectionNote]:
        """When which admin looked into the DM, oldest first (for its participants)."""
        stmt = (
            select(DmInspection.granted_at, User.name)
            .join(User, User.id == DmInspection.admin_id)
            .where(
                DmInspection.org_id == self.scope.org_id,
                DmInspection.conversation_id == conversation_id,
            )
            .order_by(DmInspection.granted_at, DmInspection.id)
        )
        return [InspectionNote(at, name) for at, name in await self.session.execute(stmt)]


class InspectionRepository:
    """DMs as an inspecting admin sees them: of the organisation, without being a
    participant. Callers have checked `dm.inspect`."""

    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def dms_of(
        self, user_id: uuid.UUID, after: tuple[uuid.UUID, uuid.UUID] | None, limit: int
    ) -> list[ListedDm]:
        """The DMs a person takes part in, by last activity."""
        of_user = and_(Conversation.org_id == self.org_id, takes_part(Principal.user(user_id)))
        return await _dm_page(self.session, of_user, after, limit)

    async def participants(
        self, conversation_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[Participant]]:
        return await participants_of(self.session, self.org_id, conversation_ids)

    async def dm(self, conversation_id: uuid.UUID) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.org_id == self.org_id,
            Conversation.id == conversation_id,
            Conversation.kind == ConversationKind.DM,
        )
        return await self.session.scalar(stmt)

    async def add(self, inspection: DmInspection) -> DmInspection:
        self.session.add(inspection)
        await self.session.flush()
        return inspection

    async def current(self, inspection_id: uuid.UUID, admin_id: uuid.UUID) -> DmInspection | None:
        """The admin's own inspection, while it lasts."""
        stmt = select(DmInspection).where(
            DmInspection.org_id == self.org_id,
            DmInspection.id == inspection_id,
            DmInspection.admin_id == admin_id,
            DmInspection.expires_at > func.now(),
        )
        return await self.session.scalar(stmt)

    async def messages(
        self, conversation_id: uuid.UUID, before: uuid.UUID | None, limit: int
    ) -> list[Message]:
        """Every message of the DM, replies included, newest first."""
        stmt = (
            select(Message)
            .where(Message.org_id == self.org_id, Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        if before is not None:
            stmt = stmt.where(Message.id < before)
        return list((await self.session.scalars(stmt)).all())
