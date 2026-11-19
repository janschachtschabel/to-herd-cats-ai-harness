"""Files whose last user is gone leave the storage only after a grace period (plan M9
decision 4). Deleting the rows writes a tombstone for each file's key in the same
transaction (`bury`); the worker's due loop removes the file GRACE later (`remove_buried`)
if it is still unused then. A backup reads the attachment rows in its database
snapshot and copies their files afterwards: every file of the snapshot is still there,
however the rows changed meanwhile (a backup that takes longer than GRACE is not
supported, docs).

What "in use" means belongs to the module that owns the files; it is passed in as
`InUse`, which also takes that module's lock on the file, so a new upload of the same
content and the removal cannot cross.
"""

import uuid
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.core.retention import upkeep_after
from app.core.storage import Storage
from app.core.storage_tombstone_repository import StorageTombstone, TombstoneRepository

__all__ = ["GRACE", "InUse", "StorageTombstone", "bury", "remove_buried"]

GRACE = upkeep_after("storage_tombstone")

InUse = Callable[[AsyncSession, uuid.UUID, str], Awaitable[bool]]


async def bury(session: AsyncSession, org_id: uuid.UUID, keys: Iterable[str]) -> None:
    """Tombstones for `keys`, in the caller's transaction; a key buried again counts
    from now."""
    await TombstoneRepository(session).bury(org_id, sorted(set(keys)), utcnow())


async def remove_buried(
    session: AsyncSession, storage: Storage, now: datetime, in_use: InUse, limit: int
) -> tuple[int, int]:
    """Up to `limit` tombstones older than GRACE at `now`, locked `SKIP LOCKED`: the
    file goes unless `in_use`, the tombstone goes either way. How many tombstones were
    taken and how many files removed. A file is removed before the commit, under the
    owner's lock; a failed commit leaves the tombstone for the next round (removing a
    file again is a no-op)."""
    tombstones = TombstoneRepository(session)
    due = await tombstones.due(now - GRACE, limit)
    removed = 0
    for tombstone in due:
        if not await in_use(session, tombstone.org_id, tombstone.storage_key):
            await storage.delete(tombstone.storage_key)
            removed += 1
    await tombstones.remove([t.id for t in due])
    return len(due), removed
