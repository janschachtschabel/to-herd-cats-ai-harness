"""`post_message` (level 3; plan M6 decision 3, spec 8.6): an agent message in a
conversation the agent belongs to, within the run's write scope.

Where: the conversation the run answers in (as a reply with `reply_to`, or at its top
level), or a channel of a space the agent is a member of. No other DM, whatever
participants it has: its audience is not the run's. Posted through `MessageService`
with the run's actor (`channel.post` in the channel's space, which the write scope
limits to the run's space), written for the agent (`kind=agent`, its run in
`run_id`), after the audience check (`writing.leaks_into`; into its own conversation
`writing.into_own_conversation`: under the personal mark, where others read along,
only with the person's release; alone with her, a marked run's message is marked
personal too). An agent's
message mentions nobody and starts no run (`MessageService.post`, `by`).
"""

import hashlib
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.errors import NotFound
from app.modules.agents.toolbox.base import NOT_FOUND, Subject, ToolContext, WriteContext
from app.modules.agents.toolbox.writing import (
    by,
    closed_to_ai,
    effect,
    into_own_conversation,
    key_for,
    leaks_into,
    refusal,
    release_first,
)
from app.modules.messaging.models import MAX_BODY_CHARS, ConversationKind
from app.modules.messaging.service import ConversationService, MessageService
from app.runtime.loop import ToolResult


class PostMessageArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_BODY_CHARS)
    ]
    reply_to: uuid.UUID | None = None


async def post_message(ctx: WriteContext, args: PostMessageArgs) -> ToolResult:
    attrs = {"conversation": str(args.conversation_id)}
    try:
        conversation = await ConversationService(ctx.session).get(ctx.actor, args.conversation_id)
    except NotFound:
        return refusal("conversation", NOT_FOUND, attrs)
    own = ctx.answers_in(conversation.id)
    shared = own and bool(await into_own_conversation(ctx, conversation.id))
    if not own and (
        conversation.kind != ConversationKind.CHANNEL
        or conversation.space_id is None
        or not await ctx.posts_in(conversation.space_id)
    ):
        return refusal("conversation", NOT_FOUND, attrs)
    if conversation.space_id is not None:
        if await closed_to_ai(ctx, conversation.space_id):
            return refusal("conversation", NOT_FOUND, attrs)
        # Its own conversation reads the run's answer anyway (`writing`, drafts).
        if why := await leaks_into(ctx, conversation.space_id, editors_only=own):
            return refusal("conversation", why, attrs)
    if shared:  # its own conversation, but others read along: her release first
        await release_first(ctx)

    async def write() -> ToolResult:
        digest = hashlib.sha256(args.text.encode()).hexdigest()
        key = key_for(ctx, "post", conversation.id, args.reply_to, digest)
        posted = await MessageService(ctx.session).post(
            ctx.actor,
            conversation.id,
            args.text,
            args.reply_to,
            client_id=key,
            by=by(ctx),
            personal=own and not shared and ctx.reads.personal,  # alone with the person
        )
        return ToolResult("conversation", f"Posted message id={posted.message.id}.", attrs)

    return await effect(ctx, "conversation", attrs, write)


async def post_subjects(ctx: ToolContext, args: PostMessageArgs) -> list[Subject] | None:
    """The conversation (a release is bound to it, `approvals/gate.py`)."""
    try:
        conversation = await ConversationService(ctx.session).get(ctx.actor, args.conversation_id)
    except NotFound:
        return None
    return [Subject("conversation", conversation.id, 0, conversation.space_id)]
