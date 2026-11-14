"""A run's cards (plan M6 task 7): what it waits for, shown where it answers.

A card is a message of the run's agent in the run's conversation (`kind` `approval`
or `question`, `client_id` the approval's or the question's id, its run in `run_id`),
posted through `MessageService` with the run's actor like any of the agent's
messages: its `message.created` event carries ids only. Its text is the approval's
summary (the tool and the ids the call names, never content of what it changes; the
diff of a page is fetched from `GET /api/approvals/{id}/diff` by the person asked) or
the agent's question. The person asked gets an activity entry (`approval` or
`question`) for the card.

Whom a card asks: the person who asked the run. (The agent's responsible person
stands in only for a run nobody asked, which M6 does not have: a run whose person is
no longer active ends `rights_revoked` before any tool call, so it never asks.)
"""

import uuid
from datetime import datetime, timedelta

from app.core.config import get_settings
from app.core.models_base import utcnow
from app.modules.agents.notices import notify
from app.modules.agents.toolbox.base import ToolContext
from app.modules.agents.toolbox.writing import by
from app.modules.messaging.models import Message, MessageKind
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.service import MessageService

# The arguments a summary names: ids, keys and choices, never a text.
NAMED = (
    "key",
    "page_id",
    "space_id",
    "parent_id",
    "status",
    "assignee_type",
    "assignee_id",
    "conversation_id",
    "reply_to",
)
MAX_SUMMARY = 500


def until() -> datetime:
    return utcnow() + timedelta(hours=get_settings().ai_approval_hours)


def summary(tool: str, args: dict[str, object]) -> str:
    named = [f"{k}={args[k]}" for k in NAMED if args.get(k) is not None]
    return (f"{tool}: {', '.join(named)}" if named else tool)[:MAX_SUMMARY]


async def post(
    ctx: ToolContext, kind: MessageKind, card_id: uuid.UUID, text: str, to: uuid.UUID
) -> Message:
    """The card, and the activity entry of the person it asks."""
    posted = await MessageService(ctx.session).post(
        ctx.actor,
        ctx.run.conversation_id,
        text,
        ctx.run.reply_to,
        client_id=card_id,
        by=by(ctx),
        card=kind,
    )
    reason = (
        NotificationReason.APPROVAL if kind == MessageKind.APPROVAL else NotificationReason.QUESTION
    )
    await notify(ctx.session, ctx.run.org_id, ctx.run.agent_id, posted.message, to, reason)
    return posted.message
