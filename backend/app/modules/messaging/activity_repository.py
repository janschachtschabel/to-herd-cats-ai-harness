"""The SQL of a person's activity view (writing notifications:
`notification_repository.py`).

The activity view filters in SQL: only the person's own notifications, only those
whose conversation the person may see now (`visible_conversations`), and only for
messages that are not deleted. A notification from a conversation gone from view
disappears from the list, the counters and the marking routes at once. A notification
bound to a proposal instead (a new page at the top level, which has no thread; plan
M6 task 6) is seen while the person may edit pages in its space (who sees proposals);
one bound to a skill proposal (plan M6 task 9) while the person sees the proposal
(`skills/sight.py`, the rule its routes use). One bound to an automation (it was
paused, plan M7) is seen while the automation exists and the person may still see
it (`automations/sight.py`: its owner, its agent's responsible person, a manager of
its place's space, `agent.manage`): it names only the automation, its agent and why
it is paused now. One bound to an account awaiting approval (plan M9 task 5b) is
seen while the person holds `user.manage`; the account is its author, and whether
it still waits comes with it.
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
    false,
    func,
    literal,
    or_,
    select,
    table,
    true,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.automations.sight import AutomationSight
from app.modules.automations.sight import seen as automation_seen
from app.modules.messaging.models import Conversation, ConversationKind, Message, MessageKind
from app.modules.messaging.notification_models import Notification, NotificationReason
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

# The same for automations (`automations` builds on messaging): its agent is the
# entry's author, its pause reason (null once it runs again) what the client words.
AUTOMATION = table(
    "automation",
    column("id", Uuid),
    column("agent_id", Uuid),
    column("paused_reason", String),
    column("owner_user_id", Uuid),
    column("conversation_id", Uuid),
    column("state", String),
)
# Its agent's responsible person, for who may see it (`automations/sight.py`).
AGENT = table("agent", column("id", Uuid), column("responsible_user_id", Uuid))


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
    automation_paused: str | None = None  # an automation's: why it is paused now
    account_awaiting: bool | None = None  # an account's: whether it still awaits approval


class ActivityRepository:
    def __init__(
        self,
        session: AsyncSession,
        scope: ConversationScope,
        skills: SkillProposalSight,
        automations: AutomationSight,
        *,
        manages_users: bool = False,
    ) -> None:
        self.session = session
        self.scope = scope
        self.skills = skills
        self.automations = automations
        self.manages_users = manages_users

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
        automation, agent = AUTOMATION.alias("seen_automation"), AGENT.alias("seen_agent")
        place = aliased(Conversation)
        sees_automation: ColumnElement[bool] = false()  # sees none: no sub-select at all
        if self.automations.sees:
            sees_automation = (
                exists()
                .where(
                    automation.c.id == Notification.automation_id,
                    automation.c.state != "deleted",  # deleted through the API: gone
                    agent.c.id == automation.c.agent_id,
                    place.id == automation.c.conversation_id,
                    automation_seen(
                        self.automations,
                        automation.c.owner_user_id,
                        agent.c.responsible_user_id,
                        place.space_id,
                    ),
                )
                .correlate_except(automation, agent, place)
            )
        about_automation = and_(Notification.automation_id.is_not(None), sees_automation)
        own_lock = and_(  # my own second factor was locked (review M9b F9)
            Notification.reason == NotificationReason.TOTP_LOCKED,
            Notification.account_id == self.scope.principal.id,
        )
        about_account = and_(
            Notification.account_id.is_not(None),
            or_(true() if self.manages_users else false(), own_lock),
        )
        return and_(
            Notification.org_id == self.scope.org_id,
            Notification.user_id == self.scope.principal.id,
            or_(bound, about_proposal, about_skill, about_automation, about_account),
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
        about_automation = Notification.automation_id.is_not(None)
        about_account = Notification.account_id.is_not(None)
        author_id = case(
            (about_account, Notification.account_id),
            (about_automation, AUTOMATION.c.agent_id),
            (about_skill, SKILL_PROPOSAL.c.author_id),
            (unbound, PROPOSAL.c.author_id),
            (system, actor),
            else_=Message.author_id,
        )
        author_type = case(
            (about_account, literal("user", String)),
            (about_automation, literal("agent", String)),
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
                AUTOMATION.c.paused_reason,
                case((about_account, User.awaiting_approval_since.is_not(None)), else_=None),
            )
            .outerjoin(Conversation, Conversation.id == Notification.conversation_id)
            .outerjoin(Message, Message.id == Notification.message_id)
            .outerjoin(PROPOSAL, PROPOSAL.c.id == Notification.proposal_id)
            .outerjoin(SKILL_PROPOSAL, SKILL_PROPOSAL.c.id == Notification.skill_proposal_id)
            .outerjoin(AUTOMATION, AUTOMATION.c.id == Notification.automation_id)
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
