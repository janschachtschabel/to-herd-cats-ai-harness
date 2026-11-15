"""`POST /api/conversations/{id}/fresh-start` ("Neu beginnen", `fresh_start.py`)."""

import uuid

from fastapi import APIRouter

from app.modules.agents.fresh_start import start_afresh
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.messaging.router import conversation_out
from app.modules.messaging.schemas import ConversationOut, ExpectedVersion

fresh_start = APIRouter(prefix="/conversations", tags=["agents"])


@fresh_start.post("/{conversation_id}/fresh-start", response_model=ConversationOut)
async def start_conversation_afresh(
    conversation_id: uuid.UUID, body: ExpectedVersion, actor: ActorDep, session: SessionDep
) -> ConversationOut:
    """Start her DM alone with an agent afresh: its runs read nothing from before now
    (the personal mark of what came before ends for them); open runs are cancelled.
    403 `conversation.not_alone_with_agent` anywhere else."""
    conversation = await start_afresh(session, actor, conversation_id, body.version)
    return await conversation_out(session, actor, conversation)
