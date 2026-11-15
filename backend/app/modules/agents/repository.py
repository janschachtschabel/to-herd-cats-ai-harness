"""The SQL of agents: the rows, what an agent's standing depends on, and its
memberships; every statement is scoped by the organisation."""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import OPEN_SPACE_FLOOR, SpaceRole
from app.core.principal import PrincipalType
from app.modules.agents.models import Agent, AgentKind, AgentStatus, AgentTool
from app.modules.agents.run_models import Run
from app.modules.ai.models import AiConnection
from app.modules.messaging.models import ConversationParticipant
from app.modules.spaces.models import Space, SpaceKind, SpaceMember
from app.modules.tokens.models import AccessToken
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class Standing:
    """What decides whether an agent may run now (`standing.refusal`)."""

    status: AgentStatus
    responsible_active: bool
    connection_enabled: bool
    connection_chat: bool
    model_listed: bool


class AgentRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def get(self, agent_id: uuid.UUID, *, lock: bool = False) -> Agent | None:
        stmt = select(Agent).where(Agent.org_id == self.org_id, Agent.id == agent_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def page(
        self, after: uuid.UUID | None, limit: int, *, owner: uuid.UUID | None = None
    ) -> list[Agent]:
        """All agents, or with `owner` only that person's personal agents."""
        stmt = select(Agent).where(Agent.org_id == self.org_id).order_by(Agent.id).limit(limit)
        if owner is not None:
            stmt = stmt.where(Agent.owner_user_id == owner)
        if after is not None:
            stmt = stmt.where(Agent.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def count_owned(self, owner: uuid.UUID) -> int:
        stmt = select(func.count()).where(Agent.org_id == self.org_id, Agent.owner_user_id == owner)
        return int(await self.session.scalar(stmt) or 0)

    async def add(self, agent: Agent) -> Agent:
        self.session.add(agent)
        await self.session.flush()
        return agent

    async def delete(self, agent: Agent) -> None:
        await self.session.execute(
            delete(SpaceMember).where(
                SpaceMember.member_type == PrincipalType.AGENT, SpaceMember.member_id == agent.id
            )
        )
        await self.session.delete(agent)
        await self.session.flush()

    async def in_use(self, agent_id: uuid.UUID) -> bool:
        """Whether the agent takes part in a conversation, has runs or (an external
        agent) was given a token (then it is paused, not deleted: what it wrote stays
        attributed, and so do its tokens' calls)."""
        talks = exists().where(
            ConversationParticipant.org_id == self.org_id,
            ConversationParticipant.principal_type == PrincipalType.AGENT,
            ConversationParticipant.principal_id == agent_id,
        )
        ran = exists().where(Run.org_id == self.org_id, Run.agent_id == agent_id)
        tokens = exists().where(AccessToken.org_id == self.org_id, AccessToken.agent_id == agent_id)
        return bool(await self.session.scalar(select(talks | ran | tokens)))

    async def responsible_names(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Each agent's responsible person's name, by agent id (one join)."""
        if not ids:
            return {}
        stmt = (
            select(Agent.id, User.name)
            .join(User, User.id == Agent.responsible_user_id)
            .where(Agent.org_id == self.org_id, User.org_id == self.org_id, Agent.id.in_(ids))
        )
        return {agent_id: name for agent_id, name in await self.session.execute(stmt)}

    async def first_member(self, ids: list[uuid.UUID], space_id: uuid.UUID) -> Agent | None:
        """The first of `ids` that is an agent, no draft, and a member of the space."""
        if not ids:
            return None
        stmt = (
            select(Agent)
            .join(
                SpaceMember,
                (SpaceMember.member_type == PrincipalType.AGENT)
                & (SpaceMember.member_id == Agent.id),
            )
            .where(
                Agent.org_id == self.org_id,
                Agent.id.in_(ids),
                Agent.status != AgentStatus.DRAFT,
                SpaceMember.space_id == space_id,
            )
        )
        found = {agent.id: agent for agent in await self.session.scalars(stmt)}
        return next((found[i] for i in ids if i in found), None)

    async def names(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not ids:
            return {}
        stmt = select(Agent.id, Agent.name).where(Agent.org_id == self.org_id, Agent.id.in_(ids))
        return {agent_id: name for agent_id, name in await self.session.execute(stmt)}

    async def external_ids(self, ids: set[uuid.UUID]) -> set[uuid.UUID]:
        """Those of `ids` that are external agents."""
        if not ids:
            return set()
        stmt = select(Agent.id).where(
            Agent.org_id == self.org_id, Agent.id.in_(ids), Agent.kind == AgentKind.EXTERNAL
        )
        return set(await self.session.scalars(stmt))

    async def standing(self, agent: Agent, connection_id: uuid.UUID, model: str) -> Standing:
        """The agent's status, its responsible person, and the connection and model it
        runs on (`standing.run_target`), as now."""
        responsible = (
            select(User.is_active)
            .where(User.org_id == self.org_id, User.id == agent.responsible_user_id)
            .scalar_subquery()
        )
        stmt = select(
            Agent.status,
            func.coalesce(responsible, False),
            AiConnection.enabled,
            AiConnection.purpose.in_(("chat", "both")),
            AiConnection.models.contains([model]),
        ).join(AiConnection, AiConnection.id == connection_id)
        row = (await self.session.execute(stmt.where(Agent.id == agent.id))).one()
        return Standing(AgentStatus(row[0]), *(bool(v) for v in row[1:]))

    async def roles(self, agent_id: uuid.UUID) -> dict[uuid.UUID, SpaceRole]:
        """The agent's role in each space it may read: its memberships, and at least
        `viewer` in the open spaces, as for a member (spec 5.3, 5.4)."""
        member = (
            select(SpaceMember.space_id, SpaceMember.role)
            .join(Space, Space.id == SpaceMember.space_id)
            .where(
                Space.org_id == self.org_id,
                SpaceMember.member_type == PrincipalType.AGENT,
                SpaceMember.member_id == agent_id,
            )
        )
        roles = {sid: SpaceRole(role) for sid, role in await self.session.execute(member)}
        open_spaces = select(Space.id).where(
            Space.org_id == self.org_id, Space.kind == SpaceKind.OPEN
        )
        for sid in await self.session.scalars(open_spaces):
            roles[sid] = max(roles.get(sid, OPEN_SPACE_FLOOR), OPEN_SPACE_FLOOR)
        return roles

    async def member_space_ids(self, agent_id: uuid.UUID) -> set[uuid.UUID]:
        """The spaces the agent is a member of (not the open ones it reads)."""
        stmt = (
            select(SpaceMember.space_id)
            .join(Space, Space.id == SpaceMember.space_id)
            .where(
                Space.org_id == self.org_id,
                SpaceMember.member_type == PrincipalType.AGENT,
                SpaceMember.member_id == agent_id,
            )
        )
        return set(await self.session.scalars(stmt))

    async def tool_entries(self, agent_id: uuid.UUID) -> dict[str, str]:
        """The agent's entries per tool (tool name → policy)."""
        stmt = select(AgentTool.tool, AgentTool.policy).where(
            AgentTool.org_id == self.org_id, AgentTool.agent_id == agent_id
        )
        return {tool: policy for tool, policy in await self.session.execute(stmt)}

    async def replace_tool_entries(self, agent_id: uuid.UUID, entries: dict[str, str]) -> None:
        await self.session.execute(
            delete(AgentTool).where(AgentTool.org_id == self.org_id, AgentTool.agent_id == agent_id)
        )
        for tool, policy in sorted(entries.items()):
            self.session.add(
                AgentTool(org_id=self.org_id, agent_id=agent_id, tool=tool, policy=policy)
            )
        await self.session.flush()

    async def of_conversation(self, conversation_id: uuid.UUID) -> Agent | None:
        """The agent taking part in a DM, if one does."""
        stmt = (
            select(Agent)
            .join(
                ConversationParticipant,
                (ConversationParticipant.principal_type == PrincipalType.AGENT)
                & (ConversationParticipant.principal_id == Agent.id),
            )
            .where(
                ConversationParticipant.org_id == self.org_id,
                ConversationParticipant.conversation_id == conversation_id,
            )
        )
        return await self.session.scalar(stmt)
