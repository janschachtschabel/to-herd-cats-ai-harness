"""Where a run answers and what it is asked there (plan M6 task 8; the triggers:
`triggers.py`, `hooks.py`).

- A DM's run reads the DM's top-level messages up to its start and answers at the
  top level; nothing to answer (its question was deleted, the agent spoke last): it
  ends `completed` at once.
- A mention's run reads the thread of the mentioning message (its root and the
  replies, up to its start) and answers there, as a reply; its question deleted: it
  ends `completed` at once.
- A ticket's run is given the ticket as its task (one turn naming its key; the model
  reads it with `read_ticket`) and answers at the top level of the ticket's thread,
  where its comments go; the ticket gone: `completed`.
"""

import uuid
from dataclasses import dataclass

from app.modules.agents.executor_repository import Claimed
from app.modules.agents.read_repository import ReadRepository
from app.modules.tickets.models import ticket_key
from app.runtime.context import Turn

TASK = (
    "The ticket {key} was assigned to you. Read it (read_ticket), work on it with your "
    "tools, and finish with a short summary of what you did: it becomes your comment in "
    "the ticket's thread."
)


@dataclass(frozen=True, slots=True)
class Asked:
    turns: list[Turn]
    reply_to: uuid.UUID | None = None  # the thread its messages go to (None: top level)


async def asked(reads: ReadRepository, claimed: Claimed) -> Asked | None:
    """What the run answers, and where (None: nothing to answer)."""
    trigger = claimed.trigger_message_id
    if trigger is None:  # a ticket's run
        assert claimed.work_item_id is not None
        number = await reads.ticket_number(claimed.work_item_id)
        if number is None:
            return None
        return Asked([Turn("person", TASK.format(key=ticket_key(number)))])
    root = await reads.thread_root(trigger)
    if root is not None:  # a mention's run
        if not await reads.present(trigger):
            return None
        said = await reads.thread(root.id, claimed.started_at)
    else:
        said = await reads.said(claimed.conversation_id, claimed.started_at)
        if not said or said[-1].by_agent:
            return None
    turns = [Turn("agent" if s.by_agent else "person", s.text) for s in said]
    return Asked(turns, root.id if root is not None else None)
