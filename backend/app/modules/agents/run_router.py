"""Run routes: my runs, an agent's runs, one run, its events, cancelling
(`run_view.py`, `runs.py`). A run one may not see answers 404 `run.not_found`."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.agents.run_schemas import MyRunsQuery, RunEventOut, RunOut, RunQuery
from app.modules.agents.run_view import RunView, RunViewService
from app.modules.agents.runs import RunService
from app.modules.auth.deps import ActorDep, SessionDep

runs = APIRouter(prefix="/runs", tags=["agents"])
agent_runs = APIRouter(prefix="/agents", tags=["agents"])


@runs.get("", response_model=Page[RunOut])
async def my_runs(
    query: Annotated[MyRunsQuery, Query()], actor: ActorDep, session: SessionDep
) -> Page[RunOut]:
    """The runs the caller asked for, newest first (`ai.use` or `agent.manage`)."""
    return _page(await RunViewService(session).mine(actor, query))


@agent_runs.get("/{agent_id}/runs", response_model=Page[RunOut])
async def runs_of_agent(
    agent_id: uuid.UUID,
    query: Annotated[RunQuery, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[RunOut]:
    """The agent's runs, newest first (its responsible person, `agent.manage`)."""
    return _page(await RunViewService(session).of_agent(actor, agent_id, query))


@runs.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> RunOut:
    return RunOut.of(await RunViewService(session).detail(actor, run_id))


@runs.post("/{run_id}/cancel", response_model=RunOut)
async def cancel_run(run_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> RunOut:
    """Stop the run (once; asking again answers the same); 409 `run.finished` if it
    ended otherwise."""
    return RunOut.of(await RunViewService(session).cancel(actor, run_id))


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


def _page(page: Page[RunView]) -> Page[RunOut]:
    return Page[RunOut](items=[RunOut.of(v) for v in page.items], next_cursor=page.next_cursor)
