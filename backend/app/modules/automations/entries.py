"""A term's system entry at its automation's place (plan M7 decision 3): in a channel
the root of the thread the term's run answers in (one thread per term), in a ticket's
thread an entry at the top level before its answer; in a DM none. Its body names the
owner (`actor`) and the automation, never the instruction; `client_id` is the term's
row in the log, so a term has one entry, and the run finds its thread by it.

Posted when the term fires, except for a heartbeat's, which its run posts only once
it has something to deliver (`runs.open_thread`): an answer `HEARTBEAT_OK` leaves no
trace (decision 7).
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.agents.notices import announce
from app.modules.automations.models import Automation
from app.modules.messaging.models import Conversation, Message
from app.modules.messaging.thread_repository import ThreadRepository

STARTED_KEY = "automation.started"


async def opened(
    session: AsyncSession, automation: Automation, place: Conversation, firing_id: uuid.UUID
) -> Message:
    """The term's entry, new (ids only in its events)."""
    body = json.dumps(
        {
            "key": STARTED_KEY,
            "actor": str(automation.owner_user_id),
            "automation_id": str(automation.id),
        }
    )
    repo = ThreadRepository(session, automation.org_id)
    message = await repo.add_system(place, firing_id, body, utcnow())
    assert message is not None  # a new term's id
    await announce(session, automation.org_id, automation.agent_id, message, system=True)
    return message
