"""The no-AI lock (spec 5.4, 11): a page or a file AI must not read, whatever the
space's policy. Set and lifted with `page.moderate` in the page's space; each is a
write that names the version it read (409 otherwise). Who may not read the page gets
the same 404 as for an unknown id. What AI may read is decided in SQL
(`ai/policy_filters.py`); a file on a locked page counts as locked too.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor
from app.core.errors import Conflict, NotFound
from app.modules.audit.recorder import record
from app.modules.wiki.attachments import attachment_not_found
from app.modules.wiki.attachments_repository import AttachmentRepository
from app.modules.wiki.models import Attachment, Page
from app.modules.wiki.visibility import PageReader, check_version, touch


class AiLockService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = PageReader(session)

    async def set_page(self, actor: Actor, page_id: uuid.UUID, no_ai: bool, version: int) -> Page:
        page = await self.reader.readable(actor, page_id, lock=True)
        await self.reader.require_in_space(actor, Action.PAGE_MODERATE, page)
        check_version(page, version)
        if page.no_ai != no_ai:
            page.no_ai = no_ai
            touch(page, actor)
            await self.session.flush()
            await record(self.session, actor, "page.ai_lock_set", "page", page.id, {"no_ai": no_ai})
        return page

    async def set_attachment(
        self, actor: Actor, attachment_id: uuid.UUID, no_ai: bool, version: int
    ) -> Attachment:
        repo = AttachmentRepository(self.session, self.reader.scope(actor))
        attachment = await repo.get(attachment_id, lock=True)
        if attachment is None:
            raise attachment_not_found()
        try:
            page = await self.reader.readable(actor, attachment.page_id)
        except NotFound:
            raise attachment_not_found() from None
        await self.reader.require_in_space(actor, Action.PAGE_MODERATE, page)
        if attachment.version != version:
            raise Conflict(
                code="attachment.version_conflict",
                details={"current_version": attachment.version},
            )
        if attachment.no_ai != no_ai:
            attachment.no_ai = no_ai
            attachment.version += 1
            await self.session.flush()
            details = {"page_id": str(page.id), "no_ai": no_ai}
            await record(
                self.session, actor, "attachment.ai_lock_set", "attachment", attachment.id, details
            )
        return attachment
