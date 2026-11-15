"""Who a write is written for, when that is not the actor whose rights it uses (spec 9,
plan M6): an agent's run acts with the rights of the person who asked, but what it
writes carries the agent as its author and the run (`run_id`): a page version, a
proposal, a message, a ticket and its events; an accepted proposal carries its author,
while the moderator who accepted it is the actor.

The rights checked stay the actor's; the author goes into what is stored and into the
change's events (`acting`), so timelines and activity name the agent.

A person's own write through an access token at `/mcp` (plan M8 decision 3) is written
for the person, with the token's name (`via_token`): the AI mark of what an external AI
client wrote. Like an agent's write it mentions nobody and starts no run.
"""

import uuid
from dataclasses import dataclass

from app.core.outbox import Acting, EventActor
from app.core.principal import Principal, PrincipalType

VIA_TOKEN_CHARS = 80  # an access token's name (`tokens/models.MAX_NAME_CHARS`)


@dataclass(frozen=True, slots=True)
class Authorship:
    principal: Principal
    run_id: uuid.UUID | None = None
    via_token: str | None = None  # the access token's name (`/mcp`), for a person

    @property
    def agent(self) -> bool:
        return self.principal.type == PrincipalType.AGENT


def acting(actor: Acting, by: Authorship | None) -> Acting:
    """Who an event names: the author written for, else the actor."""
    return EventActor(actor.org_id, by.principal) if by is not None else actor
