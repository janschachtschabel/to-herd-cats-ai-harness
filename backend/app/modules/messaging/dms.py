"""Direct messages: open and list (spec 6.1, 5.5).

A DM has 2 to 9 people, the opener included; all of them active people of the
organisation (anything else is 422 `dm.participants_invalid`, unknown ids included).
Guests answer in DMs but do not open them (403 `dm.guest_cannot_open`). Participants
never change: another group is another conversation. The same group always gets the
same conversation, also when two of them open it at once: its key (`dm_key`, a hash
of the sorted participants) is unique per organisation, and the loser of the insert
returns the winner's conversation.
"""

import hashlib
import uuid
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import Forbidden, ValidationFailed
from app.core.models_base import utcnow
from app.core.outbox import emit
from app.core.pagination import (
    Page,
    PageParams,
    decode_id_pair_cursor,
    encode_id_pair_cursor,
)
from app.core.principal import SystemRole
from app.modules.messaging.dm_repository import DmRepository, ListedDm, Participant
from app.modules.messaging.models import MAX_DM_PEOPLE, MIN_DM_PEOPLE, Conversation
from app.modules.messaging.visibility import ConversationReader


class Opened(NamedTuple):
    conversation: Conversation
    created: bool  # False: the group had its conversation already
    participants: list[Participant]


@dataclass(frozen=True, slots=True)
class DmEntry:
    conversation: Conversation
    last_message_at: datetime | None
    participants: list[Participant]


def dm_key(user_ids: Iterable[uuid.UUID]) -> str:
    """The same for the same people, whatever their order."""
    joined = "\n".join(sorted(f"user:{user_id}" for user_id in set(user_ids)))
    return hashlib.sha256(joined.encode()).hexdigest()


def participants_invalid() -> ValidationFailed:
    return ValidationFailed(
        f"{MIN_DM_PEOPLE} to {MAX_DM_PEOPLE} active people, yourself included",
        code="dm.participants_invalid",
    )


async def entry_page(
    rows: list[ListedDm],
    limit: int,
    participants: Callable[[Sequence[uuid.UUID]], Awaitable[dict[uuid.UUID, list[Participant]]]],
) -> Page[DmEntry]:
    """A page of DMs with their people; `rows` were fetched with `limit + 1`."""
    items, more = rows[:limit], len(rows) > limit
    people = await participants([row.conversation.id for row in items])
    entries = [
        DmEntry(row.conversation, row.last_message_at, people[row.conversation.id]) for row in items
    ]
    last = items[-1] if more else None
    cursor = encode_id_pair_cursor(last.activity, last.conversation.id) if last else None
    return Page[DmEntry](items=entries, next_cursor=cursor)


class DmService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = ConversationReader(session)

    def repo(self, actor: Actor) -> DmRepository:
        return DmRepository(self.session, self.reader.scope(actor))

    async def open(self, actor: Actor, user_ids: Iterable[uuid.UUID]) -> Opened:
        """The conversation of the actor and `user_ids`, opened if it is new."""
        if actor.system_role == SystemRole.GUEST:
            raise Forbidden(code="dm.guest_cannot_open")
        people = {actor.principal.id, *user_ids}
        if not MIN_DM_PEOPLE <= len(people) <= MAX_DM_PEOPLE:
            raise participants_invalid()
        repo = self.repo(actor)
        if await repo.active_people(people) != people:
            raise participants_invalid()
        key = dm_key(people)
        conversation = await repo.insert(
            {
                "dm_key": key,
                "created_by_type": actor.principal.type,
                "created_by_id": actor.principal.id,
                "created_at": utcnow(),
                "version": 1,
            }
        )
        if conversation is None:
            existing = await repo.by_key(key)
            assert existing is not None  # the conflict was with a committed row
            return Opened(existing, False, (await repo.participants([existing.id]))[existing.id])
        await repo.add_participants(conversation.id, sorted(people))
        await emit(
            self.session,
            type="dm.created",
            actor=actor,
            space_id=None,
            subject_type="conversation",
            subject_id=conversation.id,
            payload={"conversation_id": str(conversation.id)},
        )
        return Opened(
            conversation, True, (await repo.participants([conversation.id]))[conversation.id]
        )

    async def list(self, actor: Actor, params: PageParams) -> Page[DmEntry]:
        """The actor's DMs, the most recently active first."""
        after = decode_id_pair_cursor(params.cursor) if params.cursor else None
        repo = self.repo(actor)
        rows = await repo.page(after, params.limit + 1)
        return await entry_page(rows, params.limit, repo.participants)
