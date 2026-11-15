"""Usage routes: all of it for `ai.manage`, one's own with `ai.use` (else 404)."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.ai.usage import UsageService
from app.modules.ai.usage_repository import GroupBy
from app.modules.ai.usage_schemas import MyUsageOut, TotalsOut, UsageRowOut
from app.modules.auth.deps import ActorDep, SessionDep

usage = APIRouter(prefix="/ai/usage", tags=["ai"])

FirstDay = Annotated[
    date | None, Query(alias="from", description="first UTC day; default: 29 days before `to`")
]
LastDay = Annotated[date | None, Query(alias="to", description="last UTC day; default: today")]


@usage.get("", response_model=Page[UsageRowOut])
async def list_usage(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    first: FirstDay = None,
    last: LastDay = None,
    by: Annotated[GroupBy | None, Query(description="group each day further")] = None,
    run_id: Annotated[uuid.UUID | None, Query(description="only this run's calls")] = None,
) -> Page[UsageRowOut]:
    """Sums per UTC day (newest first), at most 366 days."""
    page = await UsageService(session).grouped(actor, first, last, by, run_id, params)
    return Page[UsageRowOut](
        items=[UsageRowOut.of_row(row) for row in page.items], next_cursor=page.next_cursor
    )


@usage.get("/me", response_model=MyUsageOut)
async def my_usage(
    actor: ActorDep, session: SessionDep, first: FirstDay = None, last: LastDay = None
) -> MyUsageOut:
    span, totals = await UsageService(session).mine(actor, first, last)
    return MyUsageOut(first_day=span.first, last_day=span.last, **TotalsOut.of(totals).model_dump())
