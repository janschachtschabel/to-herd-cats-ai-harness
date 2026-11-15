"""When an attachment's file may leave the storage (`core/storage_tombstones.py`): the
due loop asks `blob_in_use` for each tombstone whose grace has passed."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wiki.attachments import storage_key
from app.modules.wiki.attachments_repository import lock_blob, uses_blob


async def blob_in_use(session: AsyncSession, org_id: uuid.UUID, key: str) -> bool:
    """Whether an attachment of the organisation uses the file under `key`, under the
    content's lock (held until the transaction ends, so an upload of the same content
    waits for the removal or the removal sees the upload). A key that is not an
    attachment key of the organisation counts as in use: it is never removed here."""
    sha256 = key.rsplit("/", 1)[-1]
    if storage_key(org_id, sha256) != key:
        return True
    await lock_blob(session, org_id, sha256)
    return await uses_blob(session, org_id, sha256)
