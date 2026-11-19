"""Starting a DM alone with an agent afresh, "Neu beginnen" (module review M8 3, H2).

The personal mark (`personal_mark.py`) lasts while marked messages are in a run's
history window, since a marked answer can carry what the person read through her own
connector. Nothing unflags them; instead she can end it knowingly: a boundary on her
DM (`conversation.fresh_start_at`). Runs there after it reach nothing from before it:
not the window (`read_repository.said`), not `read_conversation` (nor a thread under a
message from before), not `search_past_runs` (no run created before it, whatever its
conversation; module review M8 4, K3). So with nothing marked in their context they
start unmarked. What stays is the agent's memory, which under the mark holds only what
she released. Earlier messages stay as they are, marked ones too.

- Only the person in her DM alone with the agent (one person, one agent) may set it:
  someone who cannot see the DM gets 404 `conversation.not_found`, anywhere else 403
  `conversation.not_alone_with_agent`; `version` as read (409
  `conversation.version_conflict`).
- The DM's row is held first (`FOR NO KEY UPDATE`), and a person's new message there
  holds it `FOR SHARE` (`MessageService.post`), so the two are serialised (module
  review M8 4, K4): a message that came first, with the run it queued, is committed
  and seen here; one that comes later waits and is written after the cut.
- The runs of the DM still open (queued, running, waiting, but not an automation's)
  are cancelled (`control.cancel`, as in the run view: a queued or waiting one ends
  at once with its notice, a running one before its next step, with its notice), so
  no run that started, or was asked, before the cut answers after it.
- The cut is the database's clock (`clock_timestamp()`), and no earlier than any
  message or run the DM holds, whatever node's clock wrote them; a message written
  after it is dated after it (`MessageService.post`). So everything before the cut
  is before it, and every run after it reads its own message.
- Audited as `conversation.fresh_start` with the number of runs cancelled, never
  content.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import Forbidden
from app.core.principal import PrincipalType
from app.modules.agents import control
from app.modules.agents.fresh_start_repository import FreshStartRepository
from app.modules.agents.run_repository import RunRepository
from app.modules.audit.recorder import record
from app.modules.messaging.dm_repository import participants_of
from app.modules.messaging.models import Conversation, ConversationKind
from app.modules.messaging.visibility import ConversationReader, check_version


async def start_afresh(
    session: AsyncSession, actor: Actor, conversation_id: uuid.UUID, version: int
) -> Conversation:
    reader = ConversationReader(session)
    conversation = await reader.readable(actor, conversation_id)
    if not await _alone_with_agent(session, actor, conversation):
        raise Forbidden(code="conversation.not_alone_with_agent")
    repo = FreshStartRepository(session, actor.org_id)
    locked = await repo.lock(conversation.id)  # a message sent meanwhile: before or after
    assert locked is not None
    check_version(locked, version)
    cancelled = 0
    for run_id in await RunRepository(session, actor.org_id).open_in(conversation.id):
        cancelled += await control.cancel(session, actor.org_id, run_id, actor.principal.id)
    locked.fresh_start_at = await repo.cut(conversation.id)  # after all it holds
    locked.version += 1
    await session.flush()
    details = {"cancelled_runs": cancelled}
    await record(session, actor, "conversation.fresh_start", "conversation", locked.id, details)
    return locked


async def _alone_with_agent(
    session: AsyncSession, actor: Actor, conversation: Conversation
) -> bool:
    if conversation.kind != ConversationKind.DM or actor.principal.type != PrincipalType.USER:
        return False
    found = (await participants_of(session, actor.org_id, [conversation.id]))[conversation.id]
    people = {p.id for p in found if p.type == PrincipalType.USER}
    agents = [p for p in found if p.type == PrincipalType.AGENT]
    return people == {actor.principal.id} and len(agents) == 1
