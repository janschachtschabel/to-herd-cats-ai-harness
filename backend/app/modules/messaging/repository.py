"""The SQL of conversations. Every statement is scoped by the actor's organisation and
by what the actor may see (`ConversationScope`), so a conversation it cannot see is
never even loaded:

- a channel: its space is one the actor may read (`access.visible_space_ids`);
- a direct message: the actor is one of its participants and still active (admins
  have no clause of their own: they read others' DMs only through an inspection).

- a page thread: its page is outside the trash, in a space the actor may read, and
  published, or the actor may edit pages there (drafts).
- a ticket thread: its space is one where the actor may read tickets (a ticket never
  leaves its space, and its thread goes with it).

Messages are seen where their conversation is (`message_repository.py`).
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, and_, exists, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_repository import person_holds_role, person_reads_space
from app.core.permissions import SPACE_ACTION_MIN_ROLE, Action
from app.core.principal import Principal, PrincipalType
from app.core.repository import advisory_xact_lock
from app.modules.messaging.models import Conversation, ConversationKind, ConversationParticipant
from app.modules.users.models import User
from app.modules.wiki.models import Page, PageStatus


@dataclass(frozen=True, slots=True)
class ConversationScope:
    org_id: uuid.UUID
    principal: Principal  # whose view it is
    space_ids: Select[uuid.UUID]  # the spaces the actor may read (SQL)
    post_space_ids: Select[uuid.UUID]  # the spaces where it holds `channel.post` (SQL)
    edit_space_ids: Select[uuid.UUID]  # the spaces where it holds `page.edit` (SQL)
    ticket_space_ids: Select[uuid.UUID]  # the spaces where it holds `ticket.read` (SQL)


def takes_part(principal: Principal) -> ColumnElement[bool]:
    """The (correlated) conversation has `principal` among its participants."""
    return exists().where(
        ConversationParticipant.conversation_id == Conversation.id,
        ConversationParticipant.principal_type == principal.type,
        ConversationParticipant.principal_id == principal.id,
    )


def visible_conversations(scope: ConversationScope) -> ColumnElement[bool]:
    """The conversations of the scope's organisation its actor may see (SQL)."""
    channel = and_(
        Conversation.kind == ConversationKind.CHANNEL,
        Conversation.space_id.in_(scope.space_ids),
    )
    active = exists().where(
        User.org_id == scope.org_id, User.id == scope.principal.id, User.is_active.is_(True)
    )
    dm = and_(Conversation.kind == ConversationKind.DM, takes_part(scope.principal), active)
    page_seen = _page_seen(
        or_(Page.status == PageStatus.PUBLISHED, Page.space_id.in_(scope.edit_space_ids))
    )
    thread = and_(
        Conversation.kind == ConversationKind.THREAD_PAGE,
        Conversation.space_id.in_(scope.space_ids),
        page_seen,
    )
    ticket = and_(
        Conversation.kind == ConversationKind.THREAD_TICKET,
        Conversation.space_id.in_(scope.ticket_space_ids),
    )
    return and_(Conversation.org_id == scope.org_id, or_(false(), channel, dm, thread, ticket))


def _page_seen(status_rule: ColumnElement[bool]) -> ColumnElement[bool]:
    """The (correlated) conversation's page is outside the trash and `status_rule`
    holds for it."""
    return (
        exists()
        .where(Page.id == Conversation.page_id, Page.trashed_at.is_(None), status_rule)
        .correlate_except(Page)
    )


def seen_by_person() -> ColumnElement[bool]:
    """`visible_conversations` from the other side: whether the (correlated) `User`
    row may see the (correlated) conversation now. Keep both in step
    (`tests/test_conversation_readers.py` compares them)."""
    channel = and_(
        Conversation.kind == ConversationKind.CHANNEL,
        person_reads_space(Conversation.space_id),
    )
    takes_part = (
        exists()
        .where(
            ConversationParticipant.conversation_id == Conversation.id,
            ConversationParticipant.principal_type == PrincipalType.USER,
            ConversationParticipant.principal_id == User.id,
        )
        .correlate_except(ConversationParticipant)
    )
    dm = and_(Conversation.kind == ConversationKind.DM, takes_part)
    edits = person_holds_role(Page.space_id, SPACE_ACTION_MIN_ROLE[Action.PAGE_EDIT])
    thread = and_(
        Conversation.kind == ConversationKind.THREAD_PAGE,
        person_reads_space(Conversation.space_id),
        _page_seen(or_(Page.status == PageStatus.PUBLISHED, edits)),
    )
    ticket = and_(
        Conversation.kind == ConversationKind.THREAD_TICKET,
        person_holds_role(Conversation.space_id, SPACE_ACTION_MIN_ROLE[Action.TICKET_READ]),
    )
    return and_(
        Conversation.org_id == User.org_id,
        User.is_active.is_(True),
        or_(false(), channel, dm, thread, ticket),
    )


async def readers_of(
    session: AsyncSession,
    org_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_ids: Iterable[uuid.UUID],
) -> set[uuid.UUID]:
    """Those of `user_ids` who may see the conversation now, in one statement. An id
    of nobody, of someone elsewhere or of someone without access is simply not in
    the answer: callers cannot tell these apart, and must not."""
    ids = list(user_ids)
    if not ids:
        return set()
    sees = (
        exists()
        .where(Conversation.id == conversation_id, seen_by_person())
        .correlate_except(Conversation)
    )
    stmt = select(User.id).where(User.org_id == org_id, User.id.in_(ids), sees)
    return set(await session.scalars(stmt))


@dataclass(frozen=True, slots=True)
class ListedConversation:
    conversation: Conversation
    can_post: bool


class ConversationRepository:
    def __init__(self, session: AsyncSession, scope: ConversationScope) -> None:
        self.session = session
        self.scope = scope

    def _visible(self) -> ColumnElement[bool]:
        return visible_conversations(self.scope)

    def _can_post(self) -> ColumnElement[bool]:
        """The right to post, before the archive (callers add that)."""
        return Conversation.space_id.in_(self.scope.post_space_ids)

    async def add(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def visible(
        self, conversation_id: uuid.UUID, *, lock: bool = False
    ) -> Conversation | None:
        """The conversation if the actor may see it; with `lock`, the row as committed
        now, locked until the transaction ends."""
        stmt = (
            select(Conversation)
            .where(self._visible(), Conversation.id == conversation_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def channel_page(
        self,
        space_id: uuid.UUID | None,
        after: tuple[str, uuid.UUID] | None,
        limit: int,
        *,
        include_archived: bool,
    ) -> list[ListedConversation]:
        """Visible channels by name (then id), of one space or of all; `after` is the
        (lower-case name, id) of the last row of the page before."""
        key = func.lower(Conversation.name)
        stmt = (
            select(Conversation, self._can_post())
            .where(self._visible(), Conversation.kind == ConversationKind.CHANNEL)
            .order_by(key, Conversation.id)
            .limit(limit)
        )
        if space_id is not None:
            stmt = stmt.where(Conversation.space_id == space_id)
        if not include_archived:
            stmt = stmt.where(Conversation.archived_at.is_(None))
        if after is not None:
            name, id_ = after
            stmt = stmt.where(or_(key > name, and_(key == name, Conversation.id > id_)))
        rows = await self.session.execute(stmt)
        return [ListedConversation(c, bool(can) and c.archived_at is None) for c, can in rows]

    async def lock_channel_names(self, space_id: uuid.UUID) -> None:
        """Serialise channel names in the space until the transaction ends, so the
        name check holds under concurrent requests (the unique index backs it up)."""
        await advisory_xact_lock(self.session, f"channel.names:{space_id}")

    async def channel_name_taken(
        self, space_id: uuid.UUID, name: str, *, besides: uuid.UUID | None = None
    ) -> bool:
        clauses = [
            Conversation.kind == ConversationKind.CHANNEL,
            Conversation.space_id == space_id,
            func.lower(Conversation.name) == name.lower(),
        ]
        if besides is not None:
            clauses.append(Conversation.id != besides)
        return bool(await self.session.scalar(select(exists().where(*clauses))))
