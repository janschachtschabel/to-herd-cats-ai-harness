"""Conversations as a whole, and their messages: post, edit, delete, list.

Writing needs the right to post in the conversation (`ConversationReader.
require_post`); editing only one's own message; deleting one's own or, with
`channel.manage`, anyone's. Deleting is soft: the text is emptied, replies stay.
A message whose conversation the actor cannot see is 404 `message.not_found`.

Posting is idempotent per author and `client_id`: a resend returns the first message
(`Posted.created` false), and nothing else happens. A new top-level message in a DM
with an agent, or a person's new message elsewhere that mentions an agent (plan M6
task 8), queues the agent's run in the same transaction, if the person and the agent
may (`agent_hooks.after_post`; `Posted.agent_run` says which run, or why none).
Posting and editing take the ids the message mentions (`mentions.py`); those who may
not see the conversation come back in `not_notified`. An agent's run posts with the
rights of the person who asked, written for the agent (`by`, plan M6 task 6): the
message is the agent's (`kind=agent`, its run in `run_id`, a `client_id` from the
tool call), mentions nobody and starts no run. Every change is emitted
(`message.created|updated|deleted`, payload ids only) in its transaction; message
text never goes into events or logs.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.authorship import Authorship, acting
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.models_base import utcnow
from app.core.outbox import emit
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.audit.recorder import record
from app.modules.messaging import mentions as mentioning
from app.modules.messaging import threads
from app.modules.messaging.agent_hooks import RunStart, agent_hooks
from app.modules.messaging.dm_repository import DmRepository, InspectionNote, Participant
from app.modules.messaging.message_repository import MessageRepository
from app.modules.messaging.models import (
    MAX_BODY_CHARS,
    Conversation,
    ConversationKind,
    Message,
    MessageKind,
)
from app.modules.messaging.visibility import ConversationReader


class Posted(NamedTuple):
    message: Message
    created: bool  # False: a resend with a known `client_id`
    not_notified: list[uuid.UUID]  # mentioned ids that were not stored (see mentions.py)
    agent_run: RunStart | None = None  # a DM with an agent, a mention: the run, or why none


class Edited(NamedTuple):
    message: Message
    not_notified: list[uuid.UUID]


def message_not_found() -> NotFound:
    return NotFound(code="message.not_found")


def checked_body(body_md: str) -> str:
    if not body_md.strip() or len(body_md) > MAX_BODY_CHARS:
        raise ValidationFailed(
            f"1 to {MAX_BODY_CHARS} characters, not only spaces", code="message.body_invalid"
        )
    return body_md


@dataclass(frozen=True, slots=True)
class ConversationView:
    """A conversation as its reader is shown it; a DM with its people and with every
    admin inspection of it (transparency towards the participants, spec 5.5)."""

    conversation: Conversation
    can_post: bool
    participants: list[Participant]
    inspections: list[InspectionNote]


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = ConversationReader(session)

    async def get(self, actor: Actor, conversation_id: uuid.UUID) -> Conversation:
        return await self.reader.readable(actor, conversation_id)

    async def can_post(self, actor: Actor, conversation: Conversation) -> bool:
        """For display; writes check again (`ConversationReader.require_post`)."""
        return await self.reader.can_post(actor, conversation)

    async def view(self, actor: Actor, conversation: Conversation) -> ConversationView:
        """For a conversation the actor has read (`get`)."""
        can_post = await self.reader.can_post(actor, conversation)
        if conversation.kind != ConversationKind.DM:
            return ConversationView(conversation, can_post, [], [])
        repo = DmRepository(self.session, self.reader.scope(actor))
        people = await repo.participants([conversation.id])
        inspections = await repo.inspections(conversation.id)
        return ConversationView(conversation, can_post, people[conversation.id], inspections)


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = ConversationReader(session)

    def repo(self, actor: Actor) -> MessageRepository:
        """The actor's view of the messages."""
        return MessageRepository(self.session, self.reader.scope(actor))

    async def post(
        self,
        actor: Actor,
        conversation_id: uuid.UUID,
        body_md: str,
        parent_id: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
        mentions: Iterable[uuid.UUID] = (),
        by: Authorship | None = None,
        card: MessageKind | None = None,
    ) -> Posted:
        """`by`: written for an agent (`kind=agent`, or `card`: an approval or a
        question card of its run, plan M6 task 7)."""
        conversation = await self.reader.readable(actor, conversation_id)
        await self.reader.require_post(actor, conversation)
        body_md = checked_body(body_md)
        asked = mentioning.asked(mentions) if by is None else []
        if by is not None and client_id is None:
            raise ValueError("an agent's message needs a client_id")
        if card is not None and by is None:
            raise ValueError("a card is an agent's")
        author = by.principal if by else actor.principal
        repo = self.repo(actor)
        parent = await threads.lock_parent(repo, conversation, parent_id) if parent_id else None
        message = await repo.insert(
            {
                "conversation_id": conversation.id,
                "parent_id": parent_id,
                "author_type": author.type,
                "author_id": author.id,
                "kind": MessageKind.HUMAN if by is None else (card or MessageKind.AGENT),
                "body_md": body_md,
                "client_id": client_id,
                "run_id": by.run_id if by else None,
                "created_at": utcnow(),
            }
        )
        if message is None:  # only with a client_id: its author sent it before
            assert client_id is not None
            first = await repo.by_client_id(author.id, client_id)
            if first is None or (first.conversation_id, first.parent_id) != (
                conversation.id,
                parent_id,
            ):
                raise Conflict(code="message.client_id_conflict")
            missed = await mentioning.not_mentioned(self.session, actor.org_id, first.id, asked)
            return Posted(first, False, missed)
        if parent is not None:
            threads.count_reply(parent, message)
            await self.session.flush()
        missed = await mentioning.mention(
            self.session, actor.org_id, conversation, message.id, asked
        )
        await self._emit(actor, conversation, message, "message.created", by)
        run = None
        if by is None:
            hooks = agent_hooks()
            run = await hooks.after_post(self.session, actor, conversation, message, asked)
        if run is not None and run.agent_id is not None:
            missed = [i for i in missed if i != run.agent_id]
        return Posted(message, True, missed, run)

    async def edit(
        self,
        actor: Actor,
        message_id: uuid.UUID,
        body_md: str,
        mentions: Iterable[uuid.UUID] | None = None,
    ) -> Edited:
        """A new text; with `mentions`, also whom the message mentions (else it keeps
        its mentions)."""
        message, conversation = await self.readable(actor, message_id, lock=True)
        await self.reader.require_post(actor, conversation)
        if not _by(message, actor):
            raise Forbidden(code="message.not_author")
        if message.deleted_at is not None:
            raise Conflict(code="message.deleted")
        message.body_md = checked_body(body_md)
        asked = mentioning.asked(mentions) if mentions is not None else None
        message.edited_at = utcnow()
        await self.session.flush()
        missed: list[uuid.UUID] = []
        if asked is not None:
            missed = await mentioning.mention(
                self.session, actor.org_id, conversation, message.id, asked
            )
        await self._emit(actor, conversation, message, "message.updated")
        return Edited(message, missed)

    async def delete(self, actor: Actor, message_id: uuid.UUID) -> None:
        message, conversation = await self.readable(actor, message_id, lock=True)
        await self.reader.require_post(actor, conversation)
        if message.kind == MessageKind.SYSTEM:  # the page's timeline stays as it was
            raise Forbidden(code="message.system")
        own = _by(message, actor)
        if not own and not await self._may_manage(actor, conversation):
            raise Forbidden(code="message.not_author")
        if message.deleted_at is not None:
            return
        message.deleted_at = utcnow()
        message.body_md = ""
        await self.session.flush()
        await self._emit(actor, conversation, message, "message.deleted")
        if not own:
            details = {"conversation_id": str(conversation.id), "author_id": str(message.author_id)}
            await record(self.session, actor, "message.moderated", "message", message.id, details)

    async def list(
        self,
        actor: Actor,
        conversation_id: uuid.UUID,
        params: PageParams,
        before: uuid.UUID | None = None,
        after: uuid.UUID | None = None,
        include_system: bool = True,
    ) -> Page[Message]:
        """Top-level messages with their reply counts: newest first (older ones page
        by page; `before` starts below a message); with `after`, oldest first from just
        after a message. Without `include_system`, no system messages (page threads)."""
        if before is not None and after is not None:
            raise ValidationFailed("before or after, not both", code="validation_failed")
        conversation = await self.reader.readable(actor, conversation_id)
        position = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).top_page(
            conversation.id,
            params.limit + 1,
            older_than=None if after else position or before,
            newer_than=position or after if after else None,
            human_only=not include_system,
        )
        return id_page(rows, params.limit, lambda m: m.id)

    async def replies(
        self, actor: Actor, message_id: uuid.UUID, params: PageParams
    ) -> Page[Message]:
        """The replies to a message, oldest first."""
        message, _ = await self.readable(actor, message_id)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).reply_page(message.id, after, params.limit + 1)
        return id_page(rows, params.limit, lambda m: m.id)

    async def readable(
        self, actor: Actor, message_id: uuid.UUID, *, lock: bool = False
    ) -> tuple[Message, Conversation]:
        """The message and its conversation, if the actor may see them (else 404
        `message.not_found`); with `lock`, the message row locked."""
        message = await self.repo(actor).get(message_id, lock=lock)
        if message is None:
            raise message_not_found()
        try:
            conversation = await self.reader.readable(actor, message.conversation_id)
        except NotFound:
            raise message_not_found() from None
        return message, conversation

    async def _may_manage(self, actor: Actor, conversation: Conversation) -> bool:
        if conversation.space_id is None:
            return False
        return await can(self.session, actor, Action.CHANNEL_MANAGE, conversation.space_id)

    async def _emit(
        self,
        actor: Actor,
        conversation: Conversation,
        message: Message,
        type_: str,
        by: Authorship | None = None,
    ) -> None:
        parent = str(message.parent_id) if message.parent_id else None
        await emit(
            self.session,
            type=type_,
            actor=acting(actor, by),
            space_id=conversation.space_id,
            subject_type="message",
            subject_id=message.id,
            payload={
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "parent_id": parent,
            },
        )


def _by(message: Message, actor: Actor) -> bool:
    return message.author_type == actor.principal.type and message.author_id == actor.principal.id
