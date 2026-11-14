"""Budget routes (`ai.manage`; anyone else: 404 `ai.not_found`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.modules.ai.budget_schemas import BudgetIn, BudgetOut
from app.modules.ai.budgets import BudgetService
from app.modules.ai.models import BudgetScope
from app.modules.auth.deps import ActorDep, SessionDep

budgets = APIRouter(prefix="/ai/budgets", tags=["ai"])


@budgets.get("", response_model=Page[BudgetOut])
async def list_budgets(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[BudgetOut]:
    """Every budget with today's use (UTC day)."""
    page = await BudgetService(session).listed(actor, params)
    return Page[BudgetOut](
        items=[BudgetOut.of(v) for v in page.items], next_cursor=page.next_cursor
    )


@budgets.put("/organisation", response_model=BudgetOut)
async def set_organisation_budget(
    body: BudgetIn, actor: ActorDep, session: SessionDep
) -> BudgetOut:
    return await _set(session, actor, BudgetScope.ORGANISATION, None, body)


@budgets.put("/users/{user_id}", response_model=BudgetOut)
async def set_user_budget(
    user_id: uuid.UUID, body: BudgetIn, actor: ActorDep, session: SessionDep
) -> BudgetOut:
    return await _set(session, actor, BudgetScope.USER, user_id, body)


@budgets.put("/agents/{agent_id}", response_model=BudgetOut)
async def set_agent_budget(
    agent_id: uuid.UUID, body: BudgetIn, actor: ActorDep, session: SessionDep
) -> BudgetOut:
    return await _set(session, actor, BudgetScope.AGENT, agent_id, body)


@budgets.delete("/{budget_id}", status_code=204)
async def delete_budget(
    budget_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> None:
    await BudgetService(session).delete(actor, budget_id, version)


async def _set(
    session: SessionDep,
    actor: Actor,
    scope: BudgetScope,
    subject_id: uuid.UUID | None,
    body: BudgetIn,
) -> BudgetOut:
    view = await BudgetService(session).set(
        actor, scope, subject_id, body.tokens_per_day, body.cost_per_day, body.version
    )
    return BudgetOut.of(view)
