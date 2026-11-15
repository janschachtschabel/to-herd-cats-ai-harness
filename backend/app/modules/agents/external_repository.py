"""What a run has sent to external MCP servers (plan M8 task 13): its cap
(`HERD_MCP_MAX_CALLS_PER_RUN`) counts the calls that went out."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import EventKind, RunEvent
from app.modules.agents.toolbox.external import OUTCOME_UNKNOWN


async def sent_calls(session: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID) -> int:
    """Every call sent has exactly one first entry, `OUTCOME_UNKNOWN`, recorded before it
    went out (`external_step.py`); a call refused or failed before that has none."""
    stmt = (
        select(func.count())
        .select_from(RunEvent)
        .where(
            RunEvent.org_id == org_id,
            RunEvent.run_id == run_id,
            RunEvent.kind == EventKind.TOOL_CALL,
            RunEvent.content["text"].astext == OUTCOME_UNKNOWN,
        )
    )
    return int(await session.scalar(stmt) or 0)
