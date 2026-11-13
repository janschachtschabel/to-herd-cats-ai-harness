"""Imports every model, so `Base.metadata` is complete (alembic, schema checks)."""

from app.core.models_base import Base
from app.core.outbox import EventDelivery, EventOutbox
from app.core.ratelimit import RateLimitHit
from app.modules.ai.models import (
    AiConnection,
    GroupAssignment,
    OrgAssignment,
    UsageRecord,
    UserAssignment,
)
from app.modules.audit.models import AuditLog
from app.modules.auth.models import UserSession
from app.modules.groups.models import Group, GroupMember
from app.modules.messaging.models import (
    Conversation,
    ConversationParticipant,
    DmInspection,
    Message,
)
from app.modules.messaging.notification_models import Notification
from app.modules.messaging.social_models import ConversationRead, MessageMention, Reaction
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space, SpaceMember
from app.modules.tags.models import Tag, Tagging
from app.modules.tickets.models import (
    Sprint,
    TicketCounter,
    TicketPageLink,
    TicketStatus,
    WorkItem,
)
from app.modules.users.models import User
from app.modules.wiki.collab_models import PageCollabState
from app.modules.wiki.models import Attachment, Page, PageVersion

__all__ = [
    "AiConnection",
    "GroupAssignment",
    "OrgAssignment",
    "UsageRecord",
    "UserAssignment",
    "Attachment",
    "AuditLog",
    "Base",
    "Conversation",
    "ConversationRead",
    "ConversationParticipant",
    "DmInspection",
    "EventDelivery",
    "EventOutbox",
    "Group",
    "GroupMember",
    "Message",
    "MessageMention",
    "Notification",
    "Organization",
    "Page",
    "PageCollabState",
    "PageVersion",
    "RateLimitHit",
    "Reaction",
    "Space",
    "SpaceMember",
    "Sprint",
    "Tag",
    "Tagging",
    "TicketCounter",
    "TicketPageLink",
    "TicketStatus",
    "User",
    "UserSession",
    "WorkItem",
]
