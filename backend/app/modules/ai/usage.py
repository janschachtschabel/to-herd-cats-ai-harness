"""Usage (spec 7.4, without budgets in M5): one record per model call or embedding
batch, written only by `record_usage`, which the agent loop and the embedding batches
call (tasks 6 and 9). Admins (`ai.manage`) read it grouped by UTC day and one of
person, agent, space or connection; a person with `ai.use` reads their own sums.

Cost: the connection's price for the model, per million tokens (EUR, input and
output); cached tokens count as input. Without a price the cost stays empty and is
not estimated (plan M5 decision 11).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor
from app.core.errors import ValidationFailed
from app.core.pagination import Page, PageParams, decode_key_cursor, encode_key_cursor
from app.modules.ai.access import require_ai
from app.modules.ai.models import UsageRecord
from app.modules.ai.repository import ConnectionRepository
from app.modules.ai.usage_repository import NO_KEY, GroupBy, Totals, UsageRepository, UsageRow

MAX_DAYS = 366
DEFAULT_DAYS = 30
MILLION = Decimal(1_000_000)


@dataclass(frozen=True, slots=True)
class Period:
    first: date
    last: date

    @property
    def start(self) -> datetime:
        return datetime.combine(self.first, time(), UTC)

    @property
    def end(self) -> datetime:
        return datetime.combine(self.last + timedelta(days=1), time(), UTC)


def period(first: date | None, last: date | None) -> Period:
    """Whole UTC days; left out: the last 30 days up to today."""
    last = last or datetime.now(UTC).date()
    first = first or last - timedelta(days=DEFAULT_DAYS - 1)
    if first > last or (last - first).days >= MAX_DAYS:
        raise ValidationFailed(code="ai.usage_period_invalid")
    return Period(first, last)


async def record_usage(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    connection_id: uuid.UUID,
    model: str,
    tokens_in: int,
    tokens_out: int,
    duration_ms: int,
    tokens_cached: int = 0,
    user_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    space_id: uuid.UUID | None = None,
) -> UsageRecord:
    """The one way usage is written, in the caller's transaction."""
    if min(tokens_in, tokens_out, tokens_cached, duration_ms) < 0 or tokens_cached > tokens_in:
        raise ValueError("usage counts out of range")
    connection = await ConnectionRepository(session, org_id).get(connection_id)
    price = (connection.prices if connection else {}).get(model)
    cost = None
    if price is not None:
        cost = (
            tokens_in * Decimal(price["input"]) + tokens_out * Decimal(price["output"])
        ) / MILLION
    record = UsageRecord(
        org_id=org_id,
        user_id=user_id,
        agent_id=agent_id,
        run_id=run_id,
        space_id=space_id,
        connection_id=connection_id,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        tokens_cached=tokens_cached,
        cost=cost,
        duration_ms=duration_ms,
    )
    return await UsageRepository(session, org_id).add(record)


class UsageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def grouped(
        self,
        actor: Actor,
        first: date | None,
        last: date | None,
        by: GroupBy | None,
        run_id: uuid.UUID | None,
        params: PageParams,
    ) -> Page[UsageRow]:
        """Newest day first; within a day by the key's id."""
        await require_ai(self.session, actor, Action.AI_MANAGE)
        span = period(first, last)
        after = _decode(params.cursor) if params.cursor else None
        repo = UsageRepository(self.session, actor.org_id)
        rows = await repo.grouped(span.start, span.end, by, run_id, after, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        end = items[-1] if more else None
        cursor = encode_key_cursor(end.day.isoformat(), end.key or NO_KEY) if end else None
        if by is not None:
            items = await repo.named(by, items)
        return Page[UsageRow](items=items, next_cursor=cursor)

    async def mine(
        self, actor: Actor, first: date | None, last: date | None
    ) -> tuple[Period, Totals]:
        """The caller's own sums; only with `ai.use` (404 otherwise)."""
        await require_ai(self.session, actor, Action.AI_USE)
        span = period(first, last)
        repo = UsageRepository(self.session, actor.org_id)
        return span, await repo.totals_of(actor.principal.id, span.start, span.end)


def _decode(cursor: str) -> tuple[date, uuid.UUID]:
    day, key = decode_key_cursor(cursor)
    try:
        return date.fromisoformat(day), key
    except ValueError as exc:
        raise ValidationFailed("Invalid cursor", code="validation_failed") from exc
