"""The run view (plan M6 decision 12; spec 8.3): lists of runs, one run with what the
view shows, and cancelling.

- **My runs** (`GET /api/runs`): the runs the caller asked for, for a person with
  `ai.use` or `agent.manage` (else 404 `ai.not_found`, as for the other AI lists).
- **An agent's runs** (`GET /api/agents/{id}/runs`): for its responsible person with
  `ai.use` and for `agent.manage`; anyone else 404 `agent.not_found`, as for an
  unknown agent.
- **One run** (`GET /api/runs/{id}`): whoever may see it (`runs.RunService.get`;
  else 404 `run.not_found`).

Each run comes with its agent's name, its asker (id and name: everyone who may see a
run is the asker, the responsible person or an agent manager, all of whom may look
people up by name), its place (the conversation's kind and id; its space, page or
ticket only where the reader reads that space), its counters, its usage totals from
the usage records (calls, tokens, cost) and whether a cancel was asked. Lists are
newest first, filtered in SQL, two statements per page whatever its length.

**Cancelling** (`POST /api/runs/{id}/cancel`): whoever may see the run may stop it
(the asker, the responsible person, `agent.manage`). The request is recorded once; a
run nobody works on (queued or waiting) ends at once as `cancelled`, a running one
before its next step or at its end (`control.cancel`). Asking again answers the same;
a run that ended otherwise answers 409 `run.finished`.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, visible_space_ids
from app.core.errors import Conflict
from app.core.pagination import Page, decode_id_cursor, encode_id_cursor
from app.modules.agents import control
from app.modules.agents.models import Agent
from app.modules.agents.repository import AgentRepository
from app.modules.agents.run_schemas import MyRunsQuery, RunQuery
from app.modules.agents.run_view_repository import (
    RunFilter,
    RunRow,
    RunTotals,
    RunViewRepository,
)
from app.modules.agents.runs import RunService, run_not_found
from app.modules.agents.standing import agent_not_found
from app.modules.ai.access import ai_not_found


@dataclass(frozen=True, slots=True)
class RunView:
    row: RunRow
    totals: RunTotals


class RunViewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def repo(self, actor: Actor) -> RunViewRepository:
        return RunViewRepository(self.session, actor.org_id)

    async def detail(self, actor: Actor, run_id: uuid.UUID) -> RunView:
        run = await RunService(self.session).get(actor, run_id)
        return await self._one(actor, run.id)

    async def mine(self, actor: Actor, query: MyRunsQuery) -> Page[RunView]:
        if not (
            await can(self.session, actor, Action.AI_USE)
            or await can(self.session, actor, Action.AGENT_MANAGE)
        ):
            raise ai_not_found()
        found = _filter(query, user_id=actor.principal.id, agent_id=query.agent_id)
        return await self._page(actor, found, query)

    async def of_agent(self, actor: Actor, agent_id: uuid.UUID, query: RunQuery) -> Page[RunView]:
        agent = await AgentRepository(self.session, actor.org_id).get(agent_id)
        if agent is None or not await self._sees_runs_of(actor, agent):
            raise agent_not_found()
        return await self._page(actor, _filter(query, agent_id=agent.id), query)

    async def cancel(self, actor: Actor, run_id: uuid.UUID) -> RunView:
        run = await RunService(self.session).get(actor, run_id)
        if not await control.cancel(self.session, actor.org_id, run.id, actor.principal.id):
            raise Conflict(code="run.finished")
        return await self._one(actor, run.id)

    async def _sees_runs_of(self, actor: Actor, agent: Agent) -> bool:
        if await can(self.session, actor, Action.AGENT_MANAGE):
            return True
        return actor.principal.id == agent.responsible_user_id and await can(
            self.session, actor, Action.AI_USE
        )

    async def _one(self, actor: Actor, run_id: uuid.UUID) -> RunView:
        rows = await self.repo(actor).rows(
            RunFilter(run_id=run_id), visible_space_ids(actor), None, 1
        )
        if not rows:
            raise run_not_found()
        return (await self._with_totals(actor, rows))[0]

    async def _page(self, actor: Actor, found: RunFilter, query: RunQuery) -> Page[RunView]:
        after = decode_id_cursor(query.cursor) if query.cursor else None
        rows = await self.repo(actor).rows(found, visible_space_ids(actor), after, query.limit + 1)
        items, more = rows[: query.limit], len(rows) > query.limit
        cursor = encode_id_cursor(items[-1].run.id) if more else None
        return Page[RunView](items=await self._with_totals(actor, items), next_cursor=cursor)

    async def _with_totals(self, actor: Actor, rows: list[RunRow]) -> list[RunView]:
        totals = await self.repo(actor).totals([row.run.id for row in rows])
        return [RunView(row, totals.get(row.run.id, RunTotals())) for row in rows]


def _filter(
    query: RunQuery, *, user_id: uuid.UUID | None = None, agent_id: uuid.UUID | None = None
) -> RunFilter:
    return RunFilter(
        user_id=user_id,
        agent_id=agent_id,
        state=query.state,
        stop_reason=query.stop_reason,
        since=query.since,
        until=query.until,
    )
