"""The SQL of a person's activity view (writing notifications:
`notification_repository.py`).

The activity view filters in SQL: only the person's own notifications, only those
whose conversation the person may see now (`visible_conversations`), and only for
messages that are not deleted. A notification from a conversation gone from view
disappears from the list, the counters and the marking routes at once. A notification
bound to a proposal instead (a new page at the top level, which has no thread; plan
M6 task 6) is seen while the person may edit pages in its space (who sees proposals);
one bound to a skill proposal (plan M6 task 9) while the person sees the proposal
(`skills/sight.py`, the rule its routes use).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import (
    ColumnElement,
    String,
    Uuid,
    and_,
    case,
    cast,
    column,
    exists,
    func,
    literal,
    or_,
    select,
    table,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.messaging.models import Conversation, ConversationKind, Message, MessageKind
from app.modules.messaging.notification_models import Notification
from app.modules.messaging.repository import ConversationScope, visible_conversations
from app.modules.messaging.ticket_hooks import ticket_hooks
from app.modules.skills.sight import SkillProposalSight
from app.modules.skills.sight import seen as skill_proposal_seen
from app.modules.users.models import User

SNIPPET_CHARS = 140

# The proposals a notification may name (`proposals` builds on messaging, so it is not
# imported): who made one, for the activity's author.
PROPOSAL = table(
    "page_proposal",
    column("id", Uuid),
    column("author_type", String),
    column("author_id", Uuid),
)
# The same for skill proposals (`skills` builds on messaging), with their space.
SKILL_PROPOSAL = table(
    "skill_proposal",
    column("id", Uuid),
    column("space_id", Uuid),
    column("author_type", String),
    column("author_id", Uuid),
)


@dataclass(frozen=True, slots=True)
class ActivityEntry:
    notification: Notification
    conversation_kind: ConversationKind | None  # None: bound to a proposal
    conversation_name: str | None
    space_id: uuid.UUID | None
    page_id: uuid.UUID | None  # a page thread's page
    ticket_number: int | None  # a ticket thread's ticket
    parent_id: uuid.UUID | None  # the thread the message is in, if any
    author_id: uuid.UUID | None
    author_name: str | None  # a person's; an agent's is named by the service
    snippet: str  # the start of the message's Markdown; empty for a timeline entry
    author_type: str | None = None  # `user` or `agent` (as the message or proposal says)


class ActivityRepository:
    def __init__(
        self, session: AsyncSession, scope: ConversationScope, skills: SkillProposalSight
    ) -> None:
        self.session = session
        self.scope = scope
        self.skills = skills

    def _mine(self) -> ColumnElement[bool]:
        # Self-contained subqueries: the list joins `conversation` and `message` too.
        seen = select(Conversation.id).where(visible_conversations(self.scope)).correlate(None)
        kept = aliased(Message)
        live = (
            select(kept.id)
            .where(kept.id == Notification.message_id, kept.deleted_at.is_(None))
            .correlate_except(kept)
        )
        bound = and_(Notification.conversation_id.in_(seen), live.exists())
        about_proposal = and_(
            Notification.proposal_id.is_not(None),
            Notification.space_id.in_(self.scope.edit_space_ids.correlate(None)),
        )
        skill = SKILL_PROPOSAL.alias("seen_skill_proposal")
        sees_skill = (
            exists()
            .where(
                skill.c.id == Notification.skill_proposal_id,
                skill_proposal_seen(
                    self.skills, skill.c.space_id, skill.c.author_type, skill.c.author_id
                ),
            )
            .correlate_except(skill)
        )
        about_skill = and_(Notification.skill_proposal_id.is_not(None), sees_skill)
        return and_(
            Notification.org_id == self.scope.org_id,
            Notification.user_id == self.scope.principal.id,
            or_(bound, about_proposal, about_skill),
        )

    async def page(
        self, before: uuid.UUID | None, limit: int, *, only_open: bool
    ) -> list[ActivityEntry]:
        """The person's notifications, newest first. A timeline entry (an assignment)
        has no author: its actor stands in, and it has no snippet (its body is a key
        and ids, which the client words). One bound to a proposal names the proposal's
        author and has no snippet either."""
        system = Message.kind == MessageKind.SYSTEM
        actor = cast(cast(Message.body_md, JSONB)["actor"].astext, Uuid)
        unbound = Notification.message_id.is_(None)
        about_skill = Notification.skill_proposal_id.is_not(None)
        author_id = case(
            (about_skill, SKILL_PROPOSAL.c.author_id),
            (unbound, PROPOSAL.c.author_id),
            (system, actor),
            else_=Message.author_id,
        )
        author_type = case(
            (about_skill, SKILL_PROPOSAL.c.author_type),
            (unbound, PROPOSAL.c.author_type),
            (system, literal(None, String)),
            else_=Message.author_type,
        )
        snippet = case(
            (or_(unbound, system), literal("")),
            else_=func.left(Message.body_md, SNIPPET_CHARS),
        )
        stmt = (
            select(
                Notification,
                Conversation.kind,
                Conversation.name,
                Conversation.space_id,
                Conversation.page_id,
                ticket_hooks().number(Conversation.work_item_id),
                Message.parent_id,
                author_id,
                User.name,
                snippet,
                author_type,
            )
            .outerjoin(Conversation, Conversation.id == Notification.conversation_id)
            .outerjoin(Message, Message.id == Notification.message_id)
            .outerjoin(PROPOSAL, PROPOSAL.c.id == Notification.proposal_id)
            .outerjoin(SKILL_PROPOSAL, SKILL_PROPOSAL.c.id == Notification.skill_proposal_id)
            .outerjoin(User, and_(User.id == author_id, User.org_id == Notification.org_id))
            .where(self._mine())
            .order_by(Notification.id.desc())
            .limit(limit)
        )
        if only_open:
            stmt = stmt.where(Notification.done_at.is_(None))
        if before is not None:
            stmt = stmt.where(Notification.id < before)
        return [ActivityEntry(*row) for row in await self.session.execute(stmt)]

    async def counts(self) -> tuple[int, int]:
        """(open, unread): not done; not done and not read."""
        open_ = Notification.done_at.is_(None)
        stmt = select(
            func.count().filter(open_),
            func.count().filter(open_, Notification.read_at.is_(None)),
        ).where(self._mine())
        row = (await self.session.execute(stmt)).one()
        return int(row[0]), int(row[1])

    async def mark(self, notification_id: uuid.UUID | None, *, done: bool) -> int:
        """Mark one notification (or, with None, every unread one) read, or done (and
        read); how many changed (a repeat changes nothing)."""
        stmt = update(Notification).where(self._mine())
        if notification_id is not None:
            stmt = stmt.where(Notification.id == notification_id)
        if done:
            stmt = stmt.where(Notification.done_at.is_(None)).values(
                done_at=func.now(), read_at=func.coalesce(Notification.read_at, func.now())
            )
        else:
            stmt = stmt.where(Notification.read_at.is_(None)).values(read_at=func.now())
        changed = await self.session.execute(stmt.returning(Notification.id))
        return len(changed.all())

    async def exists(self, notification_id: uuid.UUID) -> bool:
        stmt = select(Notification.id).where(self._mine(), Notification.id == notification_id)
        return await self.session.scalar(stmt) is not None
