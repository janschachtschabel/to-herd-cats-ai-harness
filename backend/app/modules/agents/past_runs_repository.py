"""The SQL of `search_past_runs` (`toolbox/past_runs.py`): text in the events of an
agent's earlier runs for one person, filtered in the statement by the spaces the
current run may read, and what those runs read. Scoped by the organisation."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import Select, Text, and_, cast, exists, func, literal, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.agents.run_models import EventKind, Run, RunEvent
from app.modules.spaces.models import Space


@dataclass(frozen=True, slots=True)
class PastHit:
    run_id: uuid.UUID
    conversation_id: uuid.UUID
    at: datetime
    kind: EventKind
    content: dict[str, Any]


@dataclass(slots=True)
class RunReads:
    """What a run's tool calls read: their spaces, pages and tickets, the spaces of
    the drafts among them, and whether one read through the asking person's own
    connector (the personal mark)."""

    spaces: set[uuid.UUID] = field(default_factory=set)
    pages: set[uuid.UUID] = field(default_factory=set)
    tickets: set[uuid.UUID] = field(default_factory=set)
    drafts: set[uuid.UUID] = field(default_factory=set)
    personal: bool = False


def _escaped(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PastRunRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def search(
        self,
        *,
        agent_id: uuid.UUID,
        user_id: uuid.UUID,
        exclude: uuid.UUID,
        text: str,
        readable: Select[uuid.UUID],
        conversation_id: uuid.UUID | None,
        limit: int,
        after: datetime | None = None,
    ) -> list[PastHit]:
        """Events of the agent's runs for the person (but `exclude`; with
        `conversation_id`, only runs there; with `after`, only runs created after it)
        whose text holds `text`, newest first: a
        tool result whose noted spaces are all `readable` (none noted: none), and the
        model's own words (and a final result) whose run read only `readable` spaces."""
        space = aliased(Space)  # `readable` is over `space` too: never correlated with it
        allowed = (
            select(func.coalesce(func.jsonb_agg(cast(space.id, Text)), cast("[]", JSONB)))
            .where(space.id.in_(readable))
            .scalar_subquery()
        )
        spaces = func.coalesce(RunEvent.content["spaces"], cast("[]", JSONB))
        other = aliased(RunEvent)
        other_spaces = func.coalesce(other.content["spaces"], cast("[]", JSONB))
        read_elsewhere = exists(
            select(literal(1)).where(
                other.run_id == RunEvent.run_id,
                other.kind == EventKind.TOOL_CALL,
                ~other_spaces.op("<@", is_comparison=True)(allowed),
            )
        )
        words = or_(
            RunEvent.kind == EventKind.MODEL_CALL,
            RunEvent.content["final"].astext == "true",
        )
        result = and_(
            RunEvent.kind == EventKind.TOOL_CALL,
            func.jsonb_array_length(spaces) > 0,
            spaces.op("<@", is_comparison=True)(allowed),
        )
        stmt = (
            select(
                Run.id, Run.conversation_id, RunEvent.created_at, RunEvent.kind, RunEvent.content
            )
            .join(Run, Run.id == RunEvent.run_id)
            .where(
                RunEvent.org_id == self.org_id,
                Run.org_id == self.org_id,
                Run.agent_id == agent_id,
                Run.user_id == user_id,
                Run.id != exclude,
                RunEvent.content["text"].astext.ilike(f"%{_escaped(text)}%", escape="\\"),
                or_(result, and_(words, ~read_elsewhere)),
            )
            .order_by(RunEvent.created_at.desc(), RunEvent.id.desc())
            .limit(limit)
        )
        if conversation_id is not None:
            stmt = stmt.where(Run.conversation_id == conversation_id)
        if after is not None:
            stmt = stmt.where(Run.created_at > after)
        rows = await self.session.execute(stmt)
        return [PastHit(r[0], r[1], r[2], EventKind(r[3]), r[4]) for r in rows]

    async def reads(self, run_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, RunReads]:
        """What each of the runs read, from its tool calls' events, and whether it
        carried the personal mark (also from a `mark` event)."""
        ids = sorted(set(run_ids))
        found: dict[uuid.UUID, RunReads] = {run_id: RunReads() for run_id in ids}
        if not ids:
            return found
        stmt = select(RunEvent.run_id, RunEvent.content).where(
            RunEvent.org_id == self.org_id,
            RunEvent.run_id.in_(ids),
            RunEvent.kind.in_((EventKind.TOOL_CALL, EventKind.MARK)),
        )
        for run_id, content in await self.session.execute(stmt):
            into = found[run_id]
            noted = event_reads(content)
            into.spaces |= noted.spaces
            into.pages |= noted.pages
            into.tickets |= noted.tickets
            into.drafts |= noted.drafts
            into.personal |= noted.personal
        return found


def event_reads(content: dict[str, Any]) -> RunReads:
    """What one tool call's event notes it read."""
    read = content.get("read") or {}
    return RunReads(
        _ids(content.get("spaces")),
        _ids(read.get("pages")),
        _ids(read.get("tickets")),
        _ids(read.get("drafts")),
        read.get("personal") is True,
    )


def _ids(values: object) -> set[uuid.UUID]:
    if not isinstance(values, list):
        return set()
    return {uuid.UUID(str(value)) for value in values}
