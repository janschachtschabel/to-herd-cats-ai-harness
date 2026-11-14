"""Agent and run routes. Managing agents needs `agent.manage`, an agent's profile
`ai.use`; anyone else gets 404 `agent.not_found`. Runs: see `runs.py`."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

import app.modules.agents.hooks  # noqa: F401 -- registers what messaging asks of agents
from app.core.access import Actor
from app.core.pagination import Page, PageParams
from app.modules.agents.models import Agent
from app.modules.agents.runs import RunService
from app.modules.agents.schemas import (
    AgentCreate,
    AgentOut,
    AgentProfileOut,
    AgentUpdate,
    RunEventOut,
    RunOut,
)
from app.modules.agents.service import AgentService
from app.modules.auth.deps import ActorDep, SessionDep

agents = APIRouter(prefix="/agents", tags=["agents"])
runs = APIRouter(prefix="/runs", tags=["agents"])


@agents.get("", response_model=Page[AgentOut])
async def list_agents(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[AgentOut]:
    service = AgentService(session)
    page = await service.list(actor, params)
    names = await service.responsible_names(actor, page.items)
    return Page[AgentOut](
        items=[AgentOut.of(a, names) for a in page.items], next_cursor=page.next_cursor
    )


@agents.post("", response_model=AgentOut, status_code=201)
async def create_agent(body: AgentCreate, actor: ActorDep, session: SessionDep) -> AgentOut:
    service = AgentService(session)
    return await _out(service, actor, await service.create(actor, body))


@agents.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> AgentOut:
    service = AgentService(session)
    return await _out(service, actor, await service.get(actor, agent_id))


@agents.get("/{agent_id}/profile", response_model=AgentProfileOut)
async def agent_profile(
    agent_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> AgentProfileOut:
    """For a person with `ai.use`: name, introduction and status (no draft)."""
    return AgentProfileOut.of(await AgentService(session).profile(actor, agent_id))


@agents.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID, body: AgentUpdate, actor: ActorDep, session: SessionDep
) -> AgentOut:
    service = AgentService(session)
    return await _out(service, actor, await service.update(actor, agent_id, body))


@agents.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> None:
    """Only an agent that never talked or ran (409 `agent.in_use`: pause it instead)."""
    await AgentService(session).delete(actor, agent_id, version)


async def _out(service: AgentService, actor: Actor, agent: Agent) -> AgentOut:
    return AgentOut.of(agent, await service.responsible_names(actor, [agent]))


@runs.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> RunOut:
    return RunOut.of(await RunService(session).get(actor, run_id))


@runs.get("/{run_id}/events", response_model=Page[RunEventOut])
async def run_events(
    run_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[RunEventOut]:
    page = await RunService(session).events(actor, run_id, params)
    return Page[RunEventOut](
        items=[RunEventOut.of(e) for e in page.items], next_cursor=page.next_cursor
    )
