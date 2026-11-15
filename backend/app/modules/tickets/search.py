"""Search in tickets (plan M4 task 4), for the search service (`modules/search`).

The actor's view of the tickets (the spaces where it may read them) is the whole
filter, inside the statement (`search_repository.py`). Input shaped like a key
(`HC-42`, `hc-42` or `42`, spaces around ignored) also finds that ticket and ranks it
first, if the actor may see it; otherwise the answer is the same as for a free number.
"""

import re
import uuid
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.modules.spaces.models import Space
from app.modules.tags.models import SubjectType
from app.modules.tags.repository import tag_repository
from app.modules.tickets.base import ticket_repository
from app.modules.tickets.models import KEY_PREFIX
from app.modules.tickets.repository import TicketScope
from app.modules.tickets.search_repository import TicketHit, TicketSearchRepository

__all__ = ["TicketHit", "TicketSearch", "key_number"]

_KEY = re.compile(rf"^(?:{KEY_PREFIX}-)?(\d{{1,10}})$", re.IGNORECASE)


def key_number(q: str) -> int | None:
    """The ticket number `q` names as a key, if it is one."""
    found = _KEY.match(q.strip())
    if found is None:
        return None
    number = int(found.group(1))
    return number if 1 <= number < 2**31 else None


class TicketSearch:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find(
        self,
        actor: Actor,
        q: str,
        *,
        space_id: uuid.UUID | None,
        tag_ids: Sequence[uuid.UUID],
        after: tuple[float, uuid.UUID] | None,
        limit: int,
        within: Select[uuid.UUID] | None = None,
    ) -> list[TicketHit]:
        """Best first, below `after` (score, id); with `space_id`, only that space;
        with `tag_ids`, only tickets carrying every one of them; with `within`, only
        tickets in those spaces (an agent's tool: the spaces AI may read), in the
        statement that applies the rights."""
        tags = tag_repository(self.session, actor)
        among = [tags.subject_ids(SubjectType.TICKET, [t]) for t in tag_ids]
        scope = ticket_repository(self.session, actor).scope
        if within is not None:
            scope = TicketScope(scope.org_id, scope.space_ids.where(Space.id.in_(within)))
        return await TicketSearchRepository(self.session, scope).hits(
            q, number=key_number(q), space_id=space_id, among=among, after=after, limit=limit
        )
