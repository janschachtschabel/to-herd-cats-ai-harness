"""Who a write is written for, when that is not the actor whose rights it uses (spec 9,
plan M6): an agent's run acts with the rights of the person who asked, but what it
writes carries the agent as its author and the run (`run_id`): a page version, a
proposal, a message, a ticket and its events; an accepted proposal carries its author,
while the moderator who accepted it is the actor.

The rights checked stay the actor's; the author goes into what is stored and into the
change's events (`acting`), so timelines and activity name the agent.
"""

import uuid
from dataclasses import dataclass

from app.core.outbox import Acting, EventActor
from app.core.principal import Principal


@dataclass(frozen=True, slots=True)
class Authorship:
    principal: Principal
    run_id: uuid.UUID | None = None


def acting(actor: Acting, by: Authorship | None) -> Acting:
    """Who an event names: the author written for, else the actor."""
    return EventActor(actor.org_id, by.principal) if by is not None else actor
