"""Tags on a ticket (plan M4 task 4): system-wide tags and tags of the ticket's space.

Setting them replaces the set and is a change of the ticket like any other:
`ticket.edit`, the version read (409), a new version, one `ticket.updated` event
naming `tags` (no timeline entry), and an audit entry; the same set again changes
nothing. A tag the actor cannot see is 422 `tags.not_found`, a tag of another space
422 `tags.wrong_space` (as for pages).
"""

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import ValidationFailed
from app.modules.audit.recorder import record
from app.modules.tags.models import SubjectType
from app.modules.tags.repository import tag_repository
from app.modules.tickets.base import editable, emit_change, view_of
from app.modules.tickets.events import TICKET_UPDATED, Field
from app.modules.tickets.repository import TicketView


class TicketTags:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set(
        self, actor: Actor, number: int, tag_ids: Iterable[uuid.UUID], *, version: int
    ) -> TicketView:
        repo, ticket = await editable(self.session, actor, number, version)
        wanted = list(dict.fromkeys(tag_ids))
        tags = tag_repository(self.session, actor)
        found = await tags.get_many(wanted)
        if len(found) != len(wanted):
            raise ValidationFailed(code="tags.not_found")
        if any(t.space_id not in (None, ticket.space_id) for t in found):
            raise ValidationFailed(code="tags.wrong_space")
        current = (await tags.tags_for(SubjectType.TICKET, [ticket.id])).get(ticket.id, [])
        if {t.id for t in current} == set(wanted):
            return await view_of(self.session, actor, repo, ticket.id)
        await tags.replace_for(SubjectType.TICKET, ticket.id, wanted)
        ticket.version += 1
        await self.session.flush()
        await emit_change(self.session, actor, TICKET_UPDATED, ticket, {Field.TAGS: (None, None)})
        details = {"space_id": str(ticket.space_id), "tag_ids": [str(t) for t in wanted]}
        await record(self.session, actor, "ticket.tags_set", "ticket", ticket.id, details)
        return await view_of(self.session, actor, repo, ticket.id)
