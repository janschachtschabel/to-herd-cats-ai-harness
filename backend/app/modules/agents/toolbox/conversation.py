"""The conversation tools of level 1 (plan M6 task 4).

- `read_conversation`: the conversation the run answers in, and no other: its
  arguments name no conversation, and the replies it reads must belong to a message
  of that conversation. Read through the messaging service as the person who asked
  sees it (a DM: taking part; a space's conversation: the run's rights there). The
  newest top-level messages, or those before a message, oldest first; or the replies
  to one message. Timeline notices are left out. A space's conversation names its
  space as the source (policy and rights checks of the run cover it); a DM counts as
  the person's own content, as the history does. A message marked personal is shown
  as such and marks the run (`personal_mark.py`; the host journals it with the
  result).
- `submit_result`: the run's result. It ends the run (`completed`) with its text as
  the answer; no call after it runs. Recorded like any tool call, so a run taken up
  again after it answers with it once, without a model call.
"""

import uuid
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

from app.core.errors import NotFound
from app.core.pagination import PageParams
from app.core.principal import PrincipalType
from app.modules.agents.personal_mark import PERSONAL_LINE
from app.modules.agents.toolbox.base import NOT_FOUND, ToolContext
from app.modules.messaging.models import MAX_BODY_CHARS, Message, MessageKind
from app.modules.messaging.service import ConversationService, MessageService
from app.modules.messaging.views import message_views
from app.runtime.loop import ToolResult

MESSAGES = 30


class ReadConversationArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    before: uuid.UUID | None = None
    replies_to: uuid.UUID | None = None

    @model_validator(mode="after")
    def _either(self) -> Self:
        if self.before is not None and self.replies_to is not None:
            raise ValueError("before or replies_to, not both")
        return self


class SubmitResultArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, StringConstraints(min_length=1, max_length=MAX_BODY_CHARS)]

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("not only spaces")
        return value


async def read_conversation(ctx: ToolContext, args: ReadConversationArgs) -> ToolResult:
    messages = MessageService(ctx.session)
    params = PageParams(limit=MESSAGES)
    try:
        conversation = await ConversationService(ctx.session).get(
            ctx.actor, ctx.run.conversation_id
        )
        if args.replies_to is not None:
            parent, where = await messages.readable(ctx.actor, args.replies_to)
            if where.id != conversation.id or parent.parent_id is not None:
                return ToolResult("conversation", NOT_FOUND)
            rows = (await messages.replies(ctx.actor, parent.id, params)).items
        else:
            page = await messages.list(ctx.actor, conversation.id, params, before=args.before)
            rows = list(reversed(page.items))
    except NotFound:
        return ToolResult("conversation", NOT_FOUND)
    shown = [m for m in rows if m.kind in (MessageKind.HUMAN, MessageKind.AGENT)]
    views = await message_views(ctx.session, ctx.actor, shown)
    lines = [_line(v.message, v.author_name) for v in views]
    if any(v.message.personal for v in views):
        ctx.reads.personal = True
    spaces: frozenset[uuid.UUID] = frozenset()
    if conversation.space_id is not None:
        ctx.reads.spaces.add(conversation.space_id)
        spaces = frozenset({conversation.space_id})
    return ToolResult("conversation", "\n".join(lines) or NOT_FOUND, {}, spaces)


def _line(message: Message, author: str | None) -> str:
    who = author or "someone"
    if message.author_type == PrincipalType.AGENT:
        who += " (agent)"
    body = message.body_md if message.deleted_at is None else "(deleted)"
    replies = f" [{message.reply_count} replies]" if message.reply_count else ""
    mark = PERSONAL_LINE if message.personal else ""
    return f"- {mark}id={message.id} at {message.created_at:%Y-%m-%d %H:%M} {who}{replies}: {body}"


async def submit_result(ctx: ToolContext, args: SubmitResultArgs) -> ToolResult:
    return ToolResult("result", args.text, final=True)
