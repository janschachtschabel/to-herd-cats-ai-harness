"""The SQL of live delivery: which of the open streams' login sessions may get an event
now, for all of them in one statement, and which are still valid at all.

A session counts while it has not ended (logout sets `expires_at`, deactivation and an
administrator's sign-out delete it) and its person is active. Whether that person may
see the conversation is `seen_by_person()`, the rule of `visible_conversations` from the
person's side, with groups and memberships as they are when the statement runs.
"""

import uuid
from collections.abc import Collection

from sqlalchemy import ColumnElement, and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import UserSession
from app.modules.messaging.models import Conversation
from app.modules.messaging.repository import seen_by_person
from app.modules.users.models import User


def _valid() -> ColumnElement[bool]:
    return and_(
        UserSession.expires_at > func.now(),
        User.org_id == UserSession.org_id,
        User.is_active.is_(True),
    )


async def receiving_sessions(
    session: AsyncSession,
    org_id: uuid.UUID,
    session_ids: Collection[uuid.UUID],
    *,
    conversation_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> set[uuid.UUID]:
    """Those of `session_ids` (of the organisation) whose person may get the event:
    the person `user_id` if given, and one who may see `conversation_id` if given."""
    if not session_ids or (conversation_id is None and user_id is None):
        return set()
    stmt = (
        select(UserSession.id)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.id.in_(session_ids), UserSession.org_id == org_id, _valid())
    )
    if user_id is not None:
        stmt = stmt.where(User.id == user_id)
    if conversation_id is not None:
        sees = (
            exists()
            .where(Conversation.id == conversation_id, seen_by_person())
            .correlate_except(Conversation)
        )
        stmt = stmt.where(sees)
    return set(await session.scalars(stmt))


async def valid_sessions(
    session: AsyncSession, session_ids: Collection[uuid.UUID]
) -> set[uuid.UUID]:
    """Those of `session_ids` that are still valid."""
    if not session_ids:
        return set()
    stmt = (
        select(UserSession.id)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.id.in_(session_ids), _valid())
    )
    return set(await session.scalars(stmt))
