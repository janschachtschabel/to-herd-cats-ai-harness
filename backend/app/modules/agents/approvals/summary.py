"""What an approval's summary names (module review M8 5, L1): the tool, and only values
the system resolved, never a string the model chose (an argument is the model's,
and under the personal mark it can carry what the person read through her own
connector).

- `key`: the ticket's key as the system writes it, once the run found the ticket
  where it answers (`ticket_tools.find_ticket`: the run's actor, whose read scope is
  the place's audience);
- `status`: the name of a status of that ticket's space, as the space names it;
- an id (`page_id`, `space_id`, `parent_id`, `conversation_id`): only of an object
  the release is bound to (`ToolSpec.subjects`, found by the system);
- `assignee_type`: one of its fixed choices.

A value that resolves to nothing is left out (the person asked sees the call's
arguments in full beside it). The summary is the person asked's alone
(`ApprovalOut.summary`); the card in the conversation says only the tool's name
(`gate.py`). An external tool's summary is its server and tool (`toolbox/external.py`).
"""

from typing import Any

from app.modules.agents.toolbox.base import Subject, ToolContext
from app.modules.agents.toolbox.ticket_tools import find_ticket
from app.modules.tickets.models import WorkItem, ticket_key
from app.modules.tickets.statuses import status_repository

IDS = ("page_id", "space_id", "parent_id", "conversation_id")
CHOICES = {"assignee_type": frozenset({"user", "agent"})}
MAX_SUMMARY = 500


async def summary(
    ctx: ToolContext, tool: str, args: dict[str, Any], subjects: list[Subject]
) -> str:
    named: list[str] = []
    ticket = await _ticket(ctx, args.get("key"))
    if ticket is not None:
        named.append(f"key={ticket_key(ticket.number)}")
    bound = {str(s.id) for s in subjects}
    named += [f"{k}={args[k]}" for k in IDS if args.get(k) is not None and str(args[k]) in bound]
    if ticket is not None and (status := await _status(ctx, ticket, args.get("status"))):
        named.append(f"status={status}")
    named += [f"{k}={args[k]}" for k, allowed in CHOICES.items() if args.get(k) in allowed]
    return (f"{tool}: {', '.join(named)}" if named else tool)[:MAX_SUMMARY]


async def _ticket(ctx: ToolContext, key: object) -> WorkItem | None:
    return await find_ticket(ctx, key) if isinstance(key, str) else None


async def _status(ctx: ToolContext, ticket: WorkItem, wanted: object) -> str | None:
    """The status of the ticket's space the call names (by name or id, as the tool
    finds it), as the space names it."""
    if not isinstance(wanted, str):
        return None
    folded = wanted.casefold()
    statuses = await status_repository(ctx.session, ctx.actor).in_space(ticket.space_id)
    found = next((s for s in statuses if s.name.casefold() == folded or str(s.id) == folded), None)
    return None if found is None else found.name
