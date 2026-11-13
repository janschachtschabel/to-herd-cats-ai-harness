import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.wiki.models import Attachment
from app.modules.wiki.schemas import PrincipalRef


class AttachmentOut(BaseModel):
    """`url` downloads it (`?inline=1` shows raster images in the page). `mime` is what
    the content is, whatever the upload declared. `no_ai`: locked for AI (spec 11);
    `version` guards that lock."""

    id: uuid.UUID
    page_id: uuid.UUID
    filename: str
    mime: str
    size: int
    sha256: str
    uploaded_by: PrincipalRef
    created_at: datetime
    url: str
    no_ai: bool
    version: int

    @classmethod
    def of(cls, attachment: Attachment) -> "AttachmentOut":
        return cls(
            id=attachment.id,
            page_id=attachment.page_id,
            filename=attachment.filename,
            mime=attachment.mime,
            size=attachment.size,
            sha256=attachment.sha256,
            uploaded_by=PrincipalRef(
                type=attachment.uploaded_by_type, id=attachment.uploaded_by_id
            ),
            created_at=attachment.created_at,
            url=f"/api/attachments/{attachment.id}",
            no_ai=attachment.no_ai,
            version=attachment.version,
        )
