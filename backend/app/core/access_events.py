"""`access.changed`: a person's access may have changed (a space membership or role,
directly or through a group). One outbox event per person, ids only, emitted in the
changing transaction; live delivery (`publish_live`) sends it to that person's streams
only, and the client reloads what it shows, dropping what it may no longer see
(review M3 N6). Gaining access is announced the same way, so new channels appear at
once.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Acting, emit

ACCESS_CHANGED = "access.changed"


async def access_changed(
    session: AsyncSession,
    actor: Acting,
    user_ids: Iterable[uuid.UUID],
    *,
    space_id: uuid.UUID | None,
) -> None:
    for user_id in dict.fromkeys(user_ids):
        await emit(
            session,
            type=ACCESS_CHANGED,
            actor=actor,
            space_id=space_id,
            subject_type="user",
            subject_id=user_id,
            payload={"user_id": str(user_id)},
        )
