"""A run's cards (plan M6 task 7): what it waits for, shown where it answers.

A card is a message of the run's agent in the run's conversation (`kind` `approval`
or `question`, `client_id` the approval's or the question's id, its run in `run_id`),
posted through `MessageService` with the run's actor like any of the agent's
messages: its `message.created` event carries ids only. Its text is the tool's name
for an approval (its summary, `summary.py`, and the call's arguments are the person
asked's, from `GET /api/approvals/{id}`; a page's diff from `.../diff`; module review
M8 5, L1) or the agent's question. Both are marked personal in a marked run (only
alone with the person). The person asked gets an activity entry (`approval` or
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
from app.modules.automations import runs as automation_runs
from app.modules.messaging.models import Message, MessageKind
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.service import MessageService


def until() -> datetime:
    return utcnow() + timedelta(hours=get_settings().ai_approval_hours)


async def post(
    ctx: ToolContext,
    kind: MessageKind,
    card_id: uuid.UUID,
    text: str,
    to: uuid.UUID,
    *,
    personal: bool = False,
) -> Message:
    """The card, and the activity entry of the person it asks. Where it answers: a
    heartbeat's run opens its term's thread only now (`automations/runs.py`).
    `personal`: a marked run's card alone with the person (`message.personal`)."""
    thread = ctx.run.reply_to
    if thread is None:
        opened = await automation_runs.open_thread(ctx.session, ctx.run.org_id, ctx.run.id)
        thread = opened.id if opened is not None else None
    posted = await MessageService(ctx.session).post(
        ctx.actor,
        ctx.run.conversation_id,
        text,
        thread,
        client_id=card_id,
        by=by(ctx),
        card=kind,
        personal=personal,
    )
    reason = (
        NotificationReason.APPROVAL if kind == MessageKind.APPROVAL else NotificationReason.QUESTION
    )
    await notify(ctx.session, ctx.run.org_id, ctx.run.agent_id, posted.message, to, reason)
    return posted.message
