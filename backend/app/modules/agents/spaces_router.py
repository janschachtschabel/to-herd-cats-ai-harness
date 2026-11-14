"""An agent's spaces for its managers (`agent.manage`; 404 `agent.not_found` else)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.pagination import Page, PageParams
from app.core.permissions import SpaceRole
from app.modules.agents.memberships import AgentSpaceService
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.spaces.models import SpaceKind

agent_spaces = APIRouter(prefix="/agents/{agent_id}/spaces", tags=["agents"])


class AgentSpaceOut(BaseModel):
    """A space the agent is a member of, with its `role` there."""

    id: uuid.UUID
    name: str
    kind: SpaceKind
    role: SpaceRole


@agent_spaces.get("", response_model=Page[AgentSpaceOut])
async def list_agent_spaces(
    agent_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[AgentSpaceOut]:
    """The agent's memberships by name (open spaces it only reads are not listed)."""
    page = await AgentSpaceService(session).list(actor, agent_id, params)
    items = [AgentSpaceOut(id=s.id, name=s.name, kind=s.kind, role=s.role) for s in page.items]
    return Page[AgentSpaceOut](items=items, next_cursor=page.next_cursor)
