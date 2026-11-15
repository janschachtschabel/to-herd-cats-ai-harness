"""The bounds of handing tickets to agents (`assign_ticket`; plan M6 task 8, review
M6 finding 16c).

- **Depth**: a run that came through `MAX_CHAIN_DEPTH` handovers hands over no more:
  the tool refuses (`run.handover_limit`) and the ticket's thread notes it
  (`run.refused`, the handing agent as the entry's actor).
- **Width**: one run hands at most `MAX_HANDOVERS_PER_RUN` tickets to agents, counted
  from its journal (its `assign_ticket` results marked `handover`); beyond, a tool
  error the model reads (`run.handovers`), nothing in the thread.
"""

import uuid

from app.modules.agents.notices import notice
from app.modules.agents.run_models import MAX_CHAIN_DEPTH, MAX_HANDOVERS_PER_RUN
from app.modules.agents.run_repository import RunRepository
from app.modules.agents.standing import Refusal
from app.modules.agents.toolbox.base import ToolContext
from app.modules.agents.toolbox.writing import key_for, refused
from app.modules.agents.triggers import REFUSED_KEY
from app.modules.tickets.models import WorkItem, ticket_key
from app.modules.tickets.service import TicketService
from app.runtime.loop import ToolResult

WIDTH = (
    f"Refused (run.handovers): a run hands at most {MAX_HANDOVERS_PER_RUN} tickets to "
    "agents. Assign the rest to a person, or leave them for later."
)


async def refusal(ctx: ToolContext, ticket: WorkItem, agent_id: uuid.UUID) -> ToolResult | None:
    """Why the run may not hand the ticket to the agent (None: it may)."""
    if ctx.run.chain_depth >= MAX_CHAIN_DEPTH:
        return await _too_deep(ctx, ticket, agent_id)
    handed = await RunRepository(ctx.session, ctx.run.org_id).handed_over(ctx.run.id)
    if handed >= MAX_HANDOVERS_PER_RUN:
        return ToolResult("ticket", WIDTH, {"key": ticket_key(ticket.number)})
    return None


async def _too_deep(ctx: ToolContext, ticket: WorkItem, agent_id: uuid.UUID) -> ToolResult:
    """The ticket stays as it is; its thread notes the handover that did not happen."""
    thread = await TicketService(ctx.session).thread(ctx.actor, ticket)
    content = {
        "key": REFUSED_KEY,
        "actor": str(ctx.run.agent_id),
        "to": Refusal.HANDOVER_LIMIT.value,
    }
    key = key_for(ctx, "handover", ticket.id, agent_id)
    await notice(ctx.session, ctx.run.org_id, ctx.run.agent_id, thread, key, content)
    return refused("ticket", Refusal.HANDOVER_LIMIT.value, {"key": ticket_key(ticket.number)})
