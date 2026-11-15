"""Channels: create, rename, set the topic, archive, list (spec 5.3, 6.1).

Managing needs `channel.manage` in the space; personal spaces have no channels (409
`channel.not_allowed`). Names are unique in a space ignoring case: changes to a
space's channel names are serialised, so the check holds under concurrent requests.
Every change is audited and emitted (`channel.created|updated|archived|unarchived`)
in its own transaction.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require
from app.core.errors import Conflict, NotFound
from app.core.models_base import utcnow
from app.core.outbox import emit
from app.core.pagination import PageParams, decode_key_cursor, encode_key_cursor
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.messaging.models import Conversation, ConversationKind
from app.modules.messaging.repository import ConversationRepository, ListedConversation
from app.modules.messaging.schemas import ChannelUpdate
from app.modules.messaging.visibility import ConversationReader, check_version
from app.modules.spaces.models import SpaceKind
from app.modules.spaces.repository import SpaceRepository

GENERAL_CHANNEL_NAME = "allgemein"


class ChannelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = ConversationReader(session)

    async def create(
        self, actor: Actor, space_id: uuid.UUID, name: str, topic: str | None
    ) -> Conversation:
        await require(self.session, actor, Action.CHANNEL_MANAGE, space_id)
        space = await SpaceRepository(self.session).get(actor.org_id, space_id)
        if space is None:  # only if it went away after the check
            raise NotFound(code="space.not_found")
        if space.kind == SpaceKind.PERSONAL:
            raise Conflict(code="channel.not_allowed")
        repo = self.reader.repo(actor)
        await self._name_free(repo, space_id, name)
        channel = await repo.add(
            Conversation(
                org_id=actor.org_id,
                kind=ConversationKind.CHANNEL,
                space_id=space_id,
                name=name,
                topic=topic,
                created_by_type=actor.principal.type,
                created_by_id=actor.principal.id,
            )
        )
        await self._changed(actor, channel, "channel.created", {"name": name})
        return channel

    async def create_general(self, org_id: uuid.UUID, space_id: uuid.UUID) -> Conversation:
        """`#allgemein` in the general space of a new installation (bootstrap)."""
        channel = Conversation(
            org_id=org_id,
            kind=ConversationKind.CHANNEL,
            space_id=space_id,
            name=GENERAL_CHANNEL_NAME,
        )
        self.session.add(channel)
        await self.session.flush()
        return channel

    async def list(
        self,
        actor: Actor,
        space_id: uuid.UUID | None,
        params: PageParams,
        *,
        include_archived: bool = False,
    ) -> pagination.Page[ListedConversation]:
        """The channels of every space the actor sees, or of one, by name."""
        if space_id is not None:
            await require(self.session, actor, Action.SPACE_READ, space_id)
        after = decode_key_cursor(params.cursor) if params.cursor else None
        rows = await self.reader.repo(actor).channel_page(
            space_id, after, params.limit + 1, include_archived=include_archived
        )
        items, more = rows[: params.limit], len(rows) > params.limit
        last = items[-1].conversation if more else None
        cursor = encode_key_cursor((last.name or "").lower(), last.id) if last else None
        return pagination.Page[ListedConversation](items=items, next_cursor=cursor)

    async def update(
        self, actor: Actor, conversation_id: uuid.UUID, data: ChannelUpdate
    ) -> Conversation:
        """A new name or topic (null clears the topic); fields left out stay."""
        channel = await self._manageable(actor, conversation_id)
        check_version(channel, data.version)
        before = snapshot(channel, ("name", "topic"))
        if data.name is not None and data.name != channel.name:
            assert channel.space_id is not None  # a channel's (checked by the database)
            await self._name_free(self.reader.repo(actor), channel.space_id, data.name, channel.id)
            channel.name = data.name
        if "topic" in data.model_fields_set:
            channel.topic = data.topic
        channel.version += 1
        await self.session.flush()
        changed = {"changes": changes(before, channel)}
        await self._changed(actor, channel, "channel.updated", changed)
        return channel

    async def archive(self, actor: Actor, conversation_id: uuid.UUID, version: int) -> Conversation:
        channel = await self._manageable(actor, conversation_id)
        check_version(channel, version)
        if channel.archived_at is not None:
            raise Conflict(code="conversation.archived")
        channel.archived_at = utcnow()
        channel.version += 1
        await self.session.flush()
        await self._changed(actor, channel, "channel.archived")
        return channel

    async def unarchive(
        self, actor: Actor, conversation_id: uuid.UUID, version: int
    ) -> Conversation:
        channel = await self._manageable(actor, conversation_id)
        check_version(channel, version)
        if channel.archived_at is None:
            raise Conflict(code="conversation.not_archived")
        channel.archived_at = None
        channel.version += 1
        await self.session.flush()
        await self._changed(actor, channel, "channel.unarchived")
        return channel

    async def _manageable(self, actor: Actor, conversation_id: uuid.UUID) -> Conversation:
        """The channel, locked, if the actor may manage it (404 unseen, 403 without)."""
        channel = await self.reader.readable(actor, conversation_id, lock=True)
        if channel.kind != ConversationKind.CHANNEL:
            raise Conflict(code="conversation.not_a_channel")
        await self.reader.require_in_space(actor, Action.CHANNEL_MANAGE, channel)
        return channel

    async def _name_free(
        self,
        repo: ConversationRepository,
        space_id: uuid.UUID,
        name: str,
        besides: uuid.UUID | None = None,
    ) -> None:
        await repo.lock_channel_names(space_id)
        if await repo.channel_name_taken(space_id, name, besides=besides):
            raise Conflict(code="channel.name_taken")

    async def _changed(
        self,
        actor: Actor,
        channel: Conversation,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        await record(self.session, actor, action, "conversation", channel.id, details)
        await emit(
            self.session,
            type=action,
            actor=actor,
            space_id=channel.space_id,
            subject_type="conversation",
            subject_id=channel.id,
            payload={"conversation_id": str(channel.id)},
        )
