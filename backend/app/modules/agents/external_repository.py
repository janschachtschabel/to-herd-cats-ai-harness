"""What a run has sent to external MCP servers (plan M8 task 13): its cap
(`HERD_MCP_MAX_CALLS_PER_RUN`) counts the calls that went out, by the journal's mark
`sent` (module review M8 1, finding 14), never by what a server answered."""

import uuid

from sqlalchemy import func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.run_models import EventKind, RunEvent
from app.modules.agents.toolbox.external import OUTCOME_UNKNOWN

SENT = "sent"  # a tool entry's key: true on the entry recorded before the call went out


async def sent_calls(session: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID) -> int:
    """Every call sent has exactly one first entry, recorded before it went out with
    `sent` true (`external_step.py`); a call refused or failed before that has none.
    Entries from before the mark carry no `sent` at all: there the first entry is the
    one with the placeholder's text."""
    stmt = (
        select(func.count())
        .select_from(RunEvent)
        .where(
            RunEvent.org_id == org_id,
            RunEvent.run_id == run_id,
            RunEvent.kind == EventKind.TOOL_CALL,
            or_(
                RunEvent.content[SENT].as_boolean().is_(True),
                not_(RunEvent.content.has_key(SENT))
                & (RunEvent.content["text"].astext == OUTCOME_UNKNOWN),
            ),
        )
    )
    return int(await session.scalar(stmt) or 0)
