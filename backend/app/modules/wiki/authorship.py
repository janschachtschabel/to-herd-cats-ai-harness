"""Who a write is written for, when that is not the actor whose rights it uses (spec 9,
plan M6): an agent's run acts with the rights of the person who asked, but what it
writes carries the agent as its author and the run (`run_id`); an accepted proposal
carries its author, while the moderator who accepted it is the actor.

The author goes into the version (`author_*`, `run_id`) and the page's `created_by`
or `updated_by`; the rights checked stay the actor's.
"""

import uuid
from dataclasses import dataclass

from app.core.principal import Principal


@dataclass(frozen=True, slots=True)
class Authorship:
    principal: Principal
    run_id: uuid.UUID | None = None
