"""Usage as the API shows it. `cost` (EUR) sums the calls that had a price;
`unpriced_calls` says how many had none, so an incomplete sum is not taken as whole."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.modules.ai.usage_repository import Totals, UsageRow


class TotalsOut(BaseModel):
    calls: int
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    cost: Decimal | None
    unpriced_calls: int
    duration_ms: int

    @classmethod
    def of(cls, totals: Totals) -> "TotalsOut":
        return cls(
            calls=totals.calls,
            tokens_in=totals.tokens_in,
            tokens_out=totals.tokens_out,
            tokens_cached=totals.tokens_cached,
            cost=totals.cost,
            unpriced_calls=totals.unpriced_calls,
            duration_ms=totals.duration_ms,
        )


class UsageRowOut(TotalsOut):
    """One UTC day and, when grouped, one person, agent, space or connection (`key_id`;
    null for calls without one, such as an embedding batch). `name`: the key's
    display name where known."""

    day: date
    key_id: uuid.UUID | None
    name: str | None

    @classmethod
    def of_row(cls, row: UsageRow) -> "UsageRowOut":
        return cls(
            day=row.day, key_id=row.key, name=row.name, **TotalsOut.of(row.totals).model_dump()
        )


class MyUsageOut(TotalsOut):
    """The caller's own usage in the period (whole UTC days)."""

    first_day: date
    last_day: date
