"""Runs as the API takes and shows them: the run view's filters, a run with its place
and usage, and its events (`run_view.py`, `runs.py`)."""

import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from pydantic import AwareDatetime, BaseModel

from app.core.pagination import PageParams
from app.modules.agents.models import EventKind, RunState, StopReason
from app.modules.agents.runs import ShownEvent
from app.modules.messaging.models import ConversationKind

if TYPE_CHECKING:  # run_view.py imports these schemas
    from app.modules.agents.run_view import RunView


class RunQuery(PageParams):
    """Filters of a list of runs: its state, its stop reason, and when it was created
    (`since` inclusive, `until` exclusive; with a time zone)."""

    state: RunState | None = None
    stop_reason: StopReason | None = None
    since: AwareDatetime | None = None
    until: AwareDatetime | None = None


class MyRunsQuery(RunQuery):
    """ "My runs" may also name the agent."""

    agent_id: uuid.UUID | None = None


class RunPlaceOut(BaseModel):
    """Where the run answers: the conversation's kind and id; its space, and for a
    thread its page or ticket, only where the reader reads that space (else null)."""

    kind: ConversationKind
    conversation_id: uuid.UUID
    space_id: uuid.UUID | None
    page_id: uuid.UUID | None
    ticket_number: int | None


class RunUsageOut(BaseModel):
    """The run's usage records summed: model calls, tokens (`tokens_in` includes the
    cached ones), `cost` of the priced calls (null if none had a price)."""

    calls: int
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    cost: Decimal | None


class RunOut(BaseModel):
    """A run as the run view shows it. `asker_*`: the person who asked (whose rights it
    read with, who is billed); `steps`: its model calls; `attempt`: its take-ups by a
    worker, `recoveries` those after a lost worker; `wait_until`: while `waiting`,
    when it ends unanswered; `stop_reason` once `done`; `cancel_requested`: someone
    asked it to stop. `trigger_message_id`: the message that asked (a DM's message or
    a mention; null for a run on a ticket assigned to the agent); `chain_depth`: the
    handovers from agent to agent that led to it (0: a person asked it)."""

    id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    asker_id: uuid.UUID
    asker_name: str
    conversation_id: uuid.UUID
    trigger_message_id: uuid.UUID | None
    chain_depth: int
    place: RunPlaceOut
    state: RunState
    stop_reason: StopReason | None
    attempt: int
    recoveries: int
    steps: int
    wait_until: datetime | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    usage: RunUsageOut
    cancel_requested: bool

    @classmethod
    def of(cls, view: "RunView") -> "RunOut":
        row, totals = view.row, view.totals
        run, place = row.run, row.place
        return cls(
            id=run.id,
            agent_id=run.agent_id,
            agent_name=row.agent_name,
            asker_id=run.user_id,
            asker_name=row.asker_name,
            conversation_id=run.conversation_id,
            trigger_message_id=run.trigger_message_id,
            chain_depth=run.chain_depth,
            place=RunPlaceOut(
                kind=place.kind,
                conversation_id=place.conversation_id,
                space_id=place.space_id,
                page_id=place.page_id,
                ticket_number=place.ticket_number,
            ),
            state=run.state,
            stop_reason=run.stop_reason,
            attempt=run.attempt,
            recoveries=run.recoveries,
            steps=run.steps,
            wait_until=run.wait_until,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            usage=RunUsageOut(
                calls=totals.calls,
                tokens_in=totals.tokens_in,
                tokens_out=totals.tokens_out,
                tokens_cached=totals.tokens_cached,
                cost=totals.cost,
            ),
            cancel_requested=row.cancel_requested,
        )


class RunEventOut(BaseModel):
    """One step of a run (model call: usage and the answer's parts; tool call: name,
    arguments, result, the spaces it came from; stop: the reason). `redacted`: parts
    the reader may not read are left out (`agents/runs.py`); the asking person always
    gets everything. `tokens_*`, `cost` (model calls with a price) and `duration_ms`
    (model and tool calls) where the step recorded them, null otherwise."""

    id: uuid.UUID
    attempt: int
    seq: int
    kind: EventKind
    content: dict[str, Any]
    redacted: bool
    tokens_in: int | None
    tokens_out: int | None
    tokens_cached: int | None
    cost: Decimal | None
    duration_ms: int | None
    created_at: datetime

    @classmethod
    def of(cls, shown: ShownEvent) -> "RunEventOut":
        event, content = shown.event, shown.content
        return cls(
            id=event.id,
            attempt=event.attempt,
            seq=event.seq,
            kind=event.kind,
            content=content,
            redacted=shown.redacted,
            tokens_in=_int(content.get("tokens_in")),
            tokens_out=_int(content.get("tokens_out")),
            tokens_cached=_int(content.get("tokens_cached")),
            cost=_decimal(content.get("cost")),
            duration_ms=_int(content.get("duration_ms")),
            created_at=event.created_at,
        )


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _decimal(value: object) -> Decimal | None:
    if not isinstance(value, str):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None
