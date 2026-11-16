"""Imports every model, so `Base.metadata` is complete (alembic, schema checks)."""

from app.core.models_base import Base
from app.core.outbox import EventDelivery, EventOutbox
from app.core.ratelimit import RateLimitHit
from app.core.storage_tombstone_repository import StorageTombstone
from app.modules.agents.approvals.models import Approval, RunQuestion
from app.modules.agents.memory_models import AgentMemory
from app.modules.agents.models import Agent, AgentTool
from app.modules.agents.run_control_models import RateWindow, RunCancelRequest
from app.modules.agents.run_models import Run, RunEvent
from app.modules.ai.models import (
    AiBudget,
    AiConnection,
    GroupAssignment,
    OrgAssignment,
    UsageRecord,
    UserAssignment,
)
from app.modules.audit.models import AuditLog
from app.modules.auth.models import UserSession
from app.modules.automations.event_models import AutomationEvent
from app.modules.automations.models import Automation, AutomationFiring
from app.modules.backups.models import BackupRun
from app.modules.connectors.models import Connector
from app.modules.groups.models import Group, GroupMember
from app.modules.maintenance.models import Maintenance
from app.modules.mcp_servers.models import McpServer, McpServerTool
from app.modules.mcp_tools.models import McpCall
from app.modules.messaging.models import (
    Conversation,
    ConversationParticipant,
    DmInspection,
    Message,
)
from app.modules.messaging.notification_models import Notification
from app.modules.messaging.social_models import ConversationRead, MessageMention, Reaction
from app.modules.oauth.models import OAuthClient, OAuthFlow
from app.modules.oidc.models import OidcFlow, OidcProvider, UserIdentity
from app.modules.orgs.models import Organization
from app.modules.proposals.models import PageProposal
from app.modules.skills.models import AgentSkill, Skill, SkillVersion
from app.modules.skills.proposal_models import SkillProposal
from app.modules.spaces.models import Space, SpaceMember
from app.modules.tags.models import Tag, Tagging
from app.modules.tickets.models import (
    Sprint,
    TicketCounter,
    TicketPageLink,
    TicketStatus,
    WorkItem,
)
from app.modules.tokens.models import AccessToken, McpSetting
from app.modules.totp.models import SignInChallenge, TotpRecoveryCode, UserTotp
from app.modules.users.models import User
from app.modules.wiki.collab_models import (
    CollabGrant,
    CollabInstance,
    CollabPageOwner,
    PageCollabState,
)
from app.modules.wiki.models import Attachment, Page, PageVersion

__all__ = [
    "BackupRun",
    "Maintenance",
    "StorageTombstone",
    "AccessToken",
    "McpSetting",
    "Agent",
    "AgentMemory",
    "AgentSkill",
    "AgentTool",
    "AiBudget",
    "AiConnection",
    "Approval",
    "GroupAssignment",
    "OrgAssignment",
    "UsageRecord",
    "UserAssignment",
    "RateWindow",
    "Run",
    "RunCancelRequest",
    "RunEvent",
    "RunQuestion",
    "Attachment",
    "AuditLog",
    "Automation",
    "AutomationEvent",
    "AutomationFiring",
    "Base",
    "CollabGrant",
    "CollabInstance",
    "CollabPageOwner",
    "Connector",
    "Conversation",
    "ConversationRead",
    "ConversationParticipant",
    "DmInspection",
    "EventDelivery",
    "EventOutbox",
    "Group",
    "GroupMember",
    "McpCall",
    "McpServer",
    "McpServerTool",
    "OAuthClient",
    "OAuthFlow",
    "OidcFlow",
    "OidcProvider",
    "Message",
    "MessageMention",
    "Notification",
    "Organization",
    "Page",
    "PageCollabState",
    "SkillProposal",
    "PageProposal",
    "PageVersion",
    "RateLimitHit",
    "Reaction",
    "Space",
    "Skill",
    "SkillVersion",
    "SpaceMember",
    "Sprint",
    "Tag",
    "Tagging",
    "TicketCounter",
    "TicketPageLink",
    "TicketStatus",
    "User",
    "UserIdentity",
    "UserTotp",
    "TotpRecoveryCode",
    "SignInChallenge",
    "UserSession",
    "WorkItem",
]
