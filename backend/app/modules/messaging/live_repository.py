"""The SQL of live delivery: which of the open streams' login sessions may get the
events of a batch now, for all of them in one statement, and which are still valid at
all.

A session counts while it has not ended (logout sets `expires_at`, deactivation and an
administrator's sign-out delete it) and its person is active. Whether that person may
see the conversation is `seen_by_person()`, the rule of `visible_conversations` from the
person's side, with groups and memberships as they are when the statement runs; whether
it may read a space's tickets (events for a space, plan M4b) is `person_holds_role`.
"""

import uuid
from collections.abc import Collection

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.access_repository import person_holds_role
from app.core.permissions import SPACE_ACTION_MIN_ROLE, Action
from app.modules.auth.models import UserSession
from app.modules.messaging.models import Conversation
from app.modules.messaging.repository import seen_by_person
from app.modules.spaces.models import Space
from app.modules.users.models import User


def _valid() -> ColumnElement[bool]:
    return and_(
        UserSession.expires_at > func.now(),
        User.org_id == UserSession.org_id,
        User.is_active.is_(True),
    )


async def receiving_pairs(
    session: AsyncSession,
    session_ids: Collection[uuid.UUID],
    conversation_ids: Collection[uuid.UUID],
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """Every (login session, conversation) of `session_ids` × `conversation_ids` where
    the session is valid and its person may see the conversation now, in one statement
    for a whole batch of events (any organisations: a session only ever pairs with a
    conversation of its own organisation)."""
    if not session_ids or not conversation_ids:
        return set()
    stmt = (
        select(UserSession.id, Conversation.id)
        .join(User, User.id == UserSession.user_id)
        .join(Conversation, Conversation.org_id == UserSession.org_id)
        .where(
            UserSession.id.in_(session_ids),
            Conversation.id.in_(conversation_ids),
            _valid(),
            seen_by_person(),
        )
    )
    return {(row[0], row[1]) for row in await session.execute(stmt)}


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


async def space_readers(
    session: AsyncSession,
    session_ids: Collection[uuid.UUID],
    space_ids: Collection[uuid.UUID],
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """Every (login session, space) of `session_ids` × `space_ids` where the session is
    valid and its person may read the space's tickets now, in one statement."""
    if not session_ids or not space_ids:
        return set()
    space = aliased(Space)  # the rule looks the space up again: not the same row
    stmt = (
        select(UserSession.id, space.id)
        .join(User, User.id == UserSession.user_id)
        .join(space, space.org_id == UserSession.org_id)
        .where(
            UserSession.id.in_(session_ids),
            space.id.in_(space_ids),
            _valid(),
            person_holds_role(space.id, SPACE_ACTION_MIN_ROLE[Action.TICKET_READ]),
        )
    )
    return {(row[0], row[1]) for row in await session.execute(stmt)}
