"""Budgets as the API takes and shows them. `cost_per_day` is EUR; it counts only
calls with a price, and only such calls are stopped by it (`budgets.py`)."""

import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.budgets import BudgetView, cost_reached, reached, tokens_reached
from app.modules.ai.models import BudgetScope

MAX_TOKENS_PER_DAY = 10**12
TokensPerDay = Annotated[int, Field(gt=0, le=MAX_TOKENS_PER_DAY)]
CostPerDay = Annotated[Decimal, Field(gt=0, le=1_000_000_000, max_digits=12, decimal_places=2)]


class BudgetIn(BaseModel):
    """At least one limit (422 `ai.budget_limit_missing`); `version`: the one read, or
    null to create (409 `ai.budget_version_conflict` if the subject has one meanwhile)."""

    model_config = ConfigDict(extra="forbid")

    tokens_per_day: TokensPerDay | None = None
    cost_per_day: CostPerDay | None = None
    version: int | None


class TodayOut(BaseModel):
    """Today's use (UTC day) in the budget's scope. `tokens_reached`: its token limit
    is reached (every call stops); `cost_reached`: its currency limit is reached
    (calls with a price stop, those without still count toward tokens only);
    `exhausted`: either (a priced call stops)."""

    tokens: int
    cost: Decimal
    unpriced_calls: int
    tokens_reached: bool
    cost_reached: bool
    exhausted: bool


class AgentPickOut(BaseModel):
    """An agent to set a budget for."""

    id: uuid.UUID
    name: str


class BudgetOut(BaseModel):
    id: uuid.UUID
    scope: BudgetScope
    subject_id: uuid.UUID | None  # the person or the agent; None for the organisation
    name: str | None
    tokens_per_day: int | None
    cost_per_day: Decimal | None
    version: int
    today: TodayOut

    @classmethod
    def of(cls, view: BudgetView) -> "BudgetOut":
        row, today = view.budget, view.today
        return cls(
            id=row.id,
            scope=row.scope,
            subject_id=row.subject_id,
            name=view.name,
            tokens_per_day=row.tokens_per_day,
            cost_per_day=row.cost_per_day,
            version=row.version,
            today=TodayOut(
                tokens=today.tokens,
                cost=today.cost,
                unpriced_calls=today.unpriced_calls,
                tokens_reached=tokens_reached(row, today),
                cost_reached=cost_reached(row, today),
                exhausted=reached(row, today),
            ),
        )
