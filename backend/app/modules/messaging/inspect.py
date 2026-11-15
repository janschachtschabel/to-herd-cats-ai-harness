"""The admin's inspection of direct messages (spec 5.5, plan decision 6).

Admins have no right in other people's DMs; none of the conversation routes lets
them in. The only way to read one is this service, and each step needs `dm.inspect`
(owners and admins) at the time it runs:

- `find`: the DMs a person takes part in, with names and times, never content
  (audited as `dm.admin_lookup`, once per search, not per page).
- `grant`: an inspection of one DM with a reason (10 to 500 characters), valid for
  60 minutes, written to the audit log as `dm.admin_access` with the conversation
  and the reason, and shown to the participants on the conversation.
- `messages`: the DM's messages through one's own inspection while it lasts;
  afterwards, and for anyone else, 404 `dm_inspection.not_found`. A message marked
  personal (what the person read through her own connector, in her DM with an agent;
  module review M8 2) comes withheld: its place, author and mark stay, its text is
  empty (`withheld`). It is hers alone, as the run view keeps it.

An inspection only reads: it gives no visibility anywhere else, so writing,
reacting, marking as read, search and live events stay closed to it.
"""

import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.core.errors import NotFound
from app.core.models_base import utcnow
from app.core.outbox import emit
from app.core.pagination import (
    Page,
    PageParams,
    decode_id_cursor,
    decode_id_pair_cursor,
    id_page,
)
from app.modules.audit.recorder import record
from app.modules.messaging.dm_repository import InspectionRepository
from app.modules.messaging.dms import DmEntry, entry_page
from app.modules.messaging.message_schemas import MessageOut
from app.modules.messaging.models import DmInspection, Message
from app.modules.messaging.visibility import conversation_not_found

INSPECTION_TIME = timedelta(minutes=60)


class InspectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _repo(self, actor: Actor) -> InspectionRepository:
        await require(self.session, actor, Action.DM_INSPECT)
        return InspectionRepository(self.session, actor.org_id)

    async def find(self, actor: Actor, user_id: uuid.UUID, params: PageParams) -> Page[DmEntry]:
        repo = await self._repo(actor)
        after = decode_id_pair_cursor(params.cursor) if params.cursor else None
        rows = await repo.dms_of(user_id, after, params.limit + 1)
        if after is None:
            await record(self.session, actor, "dm.admin_lookup", "user", user_id)
        return await entry_page(rows, params.limit, repo.participants)

    async def grant(self, actor: Actor, conversation_id: uuid.UUID, reason: str) -> DmInspection:
        repo = await self._repo(actor)
        dm = await repo.dm(conversation_id)
        if dm is None:
            raise conversation_not_found()
        now = utcnow()
        inspection = await repo.add(
            DmInspection(
                org_id=actor.org_id,
                conversation_id=dm.id,
                admin_id=actor.principal.id,
                reason=reason,
                granted_at=now,
                expires_at=now + INSPECTION_TIME,
            )
        )
        details = {"reason": reason, "inspection_id": str(inspection.id)}
        await record(self.session, actor, "dm.admin_access", "conversation", dm.id, details)
        await emit(
            self.session,
            type="dm.inspected",
            actor=actor,
            space_id=None,
            subject_type="conversation",
            subject_id=dm.id,
            payload={"conversation_id": str(dm.id), "inspection_id": str(inspection.id)},
        )
        return inspection

    async def messages(
        self, actor: Actor, inspection_id: uuid.UUID, params: PageParams
    ) -> Page[Message]:
        """Every message of the inspected DM, replies included, newest first."""
        repo = await self._repo(actor)
        before = decode_id_cursor(params.cursor) if params.cursor else None
        inspection = await repo.current(inspection_id, actor.principal.id)
        if inspection is None:
            raise NotFound(code="dm_inspection.not_found")
        rows = await repo.messages(inspection.conversation_id, before, params.limit + 1)
        return id_page(rows, params.limit, lambda m: m.id)


def withheld(page: Page[MessageOut]) -> Page[MessageOut]:
    """The inspected messages with the text of those marked personal left out."""
    items = [m.model_copy(update={"body_md": ""}) if m.personal else m for m in page.items]
    return Page[MessageOut](items=items, next_cursor=page.next_cursor)
