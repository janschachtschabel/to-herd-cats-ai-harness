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
- An automation's run (plan M7 decision 3) is given its instruction as its owner's
  turn, the only turn it starts with (nothing earlier of the place; its tools read
  the place like any other run's, framed as untrusted), and answers at the top level
  of the owner's DM or a ticket's thread, or in a channel in the thread its term
  opened (`automations/runs.py`); the instructions say a scheduled automation of the
  owner asks. Its term gone (the automation deleted): `completed`.

The message that asked the run is always kept when the conversation is cut to fit
(`context.window`). Only the asking person's messages are their turns and only this
agent's own earlier answers its turns; whatever else is in the thread or the DM
(other people, other agents) is context, framed as untrusted with its authors
(`runtime/context.py`). Where more than the asker read (anything but a DM alone with
the agent), `asker` names them for the instructions (review M6 finding 2).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.executor_repository import Claimed
from app.modules.agents.read_repository import ReadRepository, Said
from app.modules.agents.scope import PlaceKind, place_of
from app.modules.automations import runs as automation_runs
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
    asker: str | None = None  # the asker's name where others read too (None: alone)
    automation_of: str | None = None  # an automation's run: its owner's name


async def asked(session: AsyncSession, claimed: Claimed) -> Asked | None:
    """What the run answers, where, and for whom (None: nothing to answer)."""
    reads = ReadRepository(session, claimed.org_id)
    if claimed.automation_id is not None:
        found = await _automated(session, claimed)
    else:
        found = await _asked(reads, claimed)
    if found is None:
        return None
    place = await place_of(session, claimed.org_id, claimed.conversation_id, claimed.user_id)
    alone = place is None or place.kind == PlaceKind.ALONE
    if alone and claimed.automation_id is None:
        return found
    name = await reads.person_name(claimed.user_id) or "the person who asked"
    automation_of = name if claimed.automation_id is not None else None
    return Asked(found.turns, found.reply_to, None if alone else name, automation_of)


async def _automated(session: AsyncSession, claimed: Claimed) -> Asked | None:
    found = await automation_runs.assignment(session, claimed.org_id, claimed.id)
    if found is None:
        return None
    reply_to = found.thread.id if found.thread is not None else None
    return Asked([Turn("person", found.instruction, keep=True)], reply_to)


async def _asked(reads: ReadRepository, claimed: Claimed) -> Asked | None:
    trigger = claimed.trigger_message_id
    if trigger is None:  # a ticket's run
        assert claimed.work_item_id is not None
        number = await reads.ticket_number(claimed.work_item_id)
        if number is None:
            return None
        return Asked([Turn("person", TASK.format(key=ticket_key(number)), keep=True)])
    root = await reads.thread_root(trigger)
    if root is not None:  # a mention's run
        if not await reads.present(trigger):
            return None
        said = await reads.thread(root.id, claimed.started_at)
    else:
        said = await reads.said(claimed.conversation_id, claimed.started_at)
        if not said or said[-1].by_agent:
            return None
    turns = [_turn(s, claimed) for s in said]
    return Asked(turns, root.id if root is not None else None)


def _turn(said: Said, claimed: Claimed) -> Turn:
    if said.by_agent and said.author_id == claimed.agent_id:
        return Turn("agent", said.text)
    if not said.by_agent and said.author_id == claimed.user_id:
        asked = said.message_id is not None and said.message_id == claimed.trigger_message_id
        return Turn("person", said.text, keep=asked)  # its question stays in the window
    name = said.author_name or "someone"
    return Turn("other", said.text, f"{name} (agent)" if said.by_agent else name)
