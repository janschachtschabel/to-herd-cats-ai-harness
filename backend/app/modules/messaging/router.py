import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.messaging.channels import ChannelService
from app.modules.messaging.models import Conversation, Message
from app.modules.messaging.repository import ListedConversation
from app.modules.messaging.schemas import (
    ChannelCreate,
    ChannelUpdate,
    ConversationOut,
    ExpectedVersion,
    MessageCreate,
    MessageOut,
    MessageUpdate,
    MessageWriteOut,
)
from app.modules.messaging.service import ConversationService, MessageService
from app.modules.messaging.threads import ThreadService
from app.modules.messaging.views import message_views

space_channels = APIRouter(prefix="/spaces/{space_id}/channels", tags=["messaging"])
channels = APIRouter(prefix="/channels", tags=["messaging"])
conversations = APIRouter(prefix="/conversations", tags=["messaging"])
messages = APIRouter(prefix="/messages", tags=["messaging"])
page_threads = APIRouter(prefix="/pages/{page_id}/thread", tags=["messaging"])

ArchivedQuery = Annotated[bool, Query(description="true: archived channels too")]


def _page(page: Page[ListedConversation]) -> Page[ConversationOut]:
    return Page[ConversationOut](
        items=[ConversationOut.of(row.conversation, can_post=row.can_post) for row in page.items],
        next_cursor=page.next_cursor,
    )


async def _out(session: AsyncSession, actor: Actor, conversation: Conversation) -> ConversationOut:
    view = await ConversationService(session).view(actor, conversation)
    return ConversationOut.of(
        conversation,
        can_post=view.can_post,
        participants=view.participants,
        inspections=view.inspections,
    )


@space_channels.get("", response_model=Page[ConversationOut])
async def list_space_channels(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    include_archived: ArchivedQuery = False,
) -> Page[ConversationOut]:
    page = await ChannelService(session).list(
        actor, space_id, params, include_archived=include_archived
    )
    return _page(page)


@space_channels.post("", response_model=ConversationOut, status_code=201)
async def create_channel(
    space_id: uuid.UUID, body: ChannelCreate, actor: ActorDep, session: SessionDep
) -> ConversationOut:
    channel = await ChannelService(session).create(actor, space_id, body.name, body.topic)
    return await _out(session, actor, channel)


@channels.get("", response_model=Page[ConversationOut])
async def list_channels(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    include_archived: ArchivedQuery = False,
) -> Page[ConversationOut]:
    """The channels of every space the caller may read, by name."""
    page = await ChannelService(session).list(
        actor, None, params, include_archived=include_archived
    )
    return _page(page)


@conversations.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> ConversationOut:
    conversation = await ConversationService(session).get(actor, conversation_id)
    return await _out(session, actor, conversation)


@conversations.patch("/{conversation_id}", response_model=ConversationOut)
async def update_channel(
    conversation_id: uuid.UUID, body: ChannelUpdate, actor: ActorDep, session: SessionDep
) -> ConversationOut:
    channel = await ChannelService(session).update(actor, conversation_id, body)
    return await _out(session, actor, channel)


@conversations.post("/{conversation_id}/archive", response_model=ConversationOut)
async def archive_channel(
    conversation_id: uuid.UUID, body: ExpectedVersion, actor: ActorDep, session: SessionDep
) -> ConversationOut:
    channel = await ChannelService(session).archive(actor, conversation_id, body.version)
    return await _out(session, actor, channel)


@conversations.post("/{conversation_id}/unarchive", response_model=ConversationOut)
async def unarchive_channel(
    conversation_id: uuid.UUID, body: ExpectedVersion, actor: ActorDep, session: SessionDep
) -> ConversationOut:
    channel = await ChannelService(session).unarchive(actor, conversation_id, body.version)
    return await _out(session, actor, channel)


async def message_page(
    session: AsyncSession, actor: Actor, page: Page[Message]
) -> Page[MessageOut]:
    views = await message_views(session, actor, page.items)
    return Page[MessageOut](items=[MessageOut.of(v) for v in views], next_cursor=page.next_cursor)


async def _written(
    session: AsyncSession, actor: Actor, message: Message, not_notified: list[uuid.UUID]
) -> MessageWriteOut:
    (view,) = await message_views(session, actor, [message])
    return MessageWriteOut(**MessageOut.of(view).model_dump(), not_notified=not_notified)


@conversations.get("/{conversation_id}/messages", response_model=Page[MessageOut])
async def list_messages(
    conversation_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    before: Annotated[
        uuid.UUID | None, Query(description="start below this message (newest first)")
    ] = None,
    after: Annotated[
        uuid.UUID | None, Query(description="oldest first, from just after this message")
    ] = None,
    include_system: Annotated[
        bool, Query(description="false: without system messages (page threads)")
    ] = True,
) -> Page[MessageOut]:
    """Top-level messages with their reply counts, newest first."""
    page = await MessageService(session).list(
        actor, conversation_id, params, before=before, after=after, include_system=include_system
    )
    return await message_page(session, actor, page)


@conversations.post(
    "/{conversation_id}/messages",
    response_model=MessageWriteOut,
    status_code=201,
    responses={200: {"model": MessageWriteOut, "description": "sent before with this client_id"}},
)
async def post_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    response: Response,
    actor: ActorDep,
    session: SessionDep,
) -> MessageWriteOut:
    posted = await MessageService(session).post(
        actor,
        conversation_id,
        body.body_md,
        parent_id=body.parent_id,
        client_id=body.client_id,
        mentions=body.mentions,
    )
    if not posted.created:
        response.status_code = 200
    return await _written(session, actor, posted.message, posted.not_notified)


@messages.get("/{message_id}/replies", response_model=Page[MessageOut])
async def list_replies(
    message_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[MessageOut]:
    """The message's thread, oldest first."""
    page = await MessageService(session).replies(actor, message_id, params)
    return await message_page(session, actor, page)


@messages.patch("/{message_id}", response_model=MessageWriteOut)
async def edit_message(
    message_id: uuid.UUID, body: MessageUpdate, actor: ActorDep, session: SessionDep
) -> MessageWriteOut:
    edited = await MessageService(session).edit(actor, message_id, body.body_md, body.mentions)
    return await _written(session, actor, edited.message, edited.not_notified)


@messages.delete("/{message_id}", status_code=204)
async def delete_message(message_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await MessageService(session).delete(actor, message_id)


@page_threads.get("", response_model=ConversationOut)
async def get_page_thread(
    page_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> ConversationOut:
    """The page's discussion (created on first access), for whoever sees the page;
    its messages come from `/conversations/{id}/messages`."""
    thread = await ThreadService(session).for_page(actor, page_id)
    return await _out(session, actor, thread)
