"""A run and its events as people read them (spec 8.3; the run view itself comes with
M6). A run is visible to the person who asked and to the agent's responsible person,
each while they have `ai.use`, and to holders of `agent.manage`; to anyone else it
answers 404 `run.not_found`, as for an unknown id."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.errors import NotFound
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.agents.models import Run, RunEvent
from app.modules.agents.run_repository import RunRepository


def run_not_found() -> NotFound:
    return NotFound(code="run.not_found")


class RunService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, actor: Actor, run_id: uuid.UUID) -> Run:
        found = await RunRepository(self.session, actor.org_id).get(run_id)
        if found is None:
            raise run_not_found()
        run, agent = found
        if await can(self.session, actor, Action.AGENT_MANAGE):
            return run
        involved = actor.principal.id in (run.user_id, agent.responsible_user_id)
        if involved and await can(self.session, actor, Action.AI_USE):
            return run
        raise run_not_found()

    async def events(self, actor: Actor, run_id: uuid.UUID, params: PageParams) -> Page[RunEvent]:
        """The run's events, in the order they happened."""
        run = await self.get(actor, run_id)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await RunRepository(self.session, actor.org_id).events(
            run.id, after, params.limit + 1
        )
        return id_page(rows, params.limit, lambda e: e.id)
