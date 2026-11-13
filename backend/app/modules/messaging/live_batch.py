"""A batch of live events to the open streams that may have them (review M3 N1).

The hub takes whatever is queued (at most BATCH_SIZE events) and answers who may get
each of them in at most three statements for the whole batch, whatever its size:

- `receiving_pairs`: every (login session, conversation) of the batch where the
  session is valid and its person may see the conversation now;
- `valid_sessions`: the valid sessions among those an event without a conversation
  is for (one person's own events);
- `space_readers`: every (login session, space) where the session is valid and its
  person may read the space's tickets now (sprint events, plan M4b).

Nothing is remembered between batches, so a membership removed while a stream is
open stops the next batch already. When the check fails (database error), every
stream the batch was for gets `resync` instead. Frames go out in the order the
events came; each event's lag (NOTIFY received → handed to its streams) is observed.
"""

import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.db import Database
from app.modules.messaging.live_connection import RESYNC, Connection
from app.modules.messaging.live_events import LiveEvent
from app.modules.messaging.live_repository import receiving_pairs, space_readers, valid_sessions
from app.modules.messaging.metrics import LIVE_DELIVERY_LAG, LIVE_RESYNCS

logger = logging.getLogger(__name__)

BATCH_SIZE = 200


@dataclass(frozen=True, slots=True)
class Received:
    event: LiveEvent
    at: float  # time.monotonic() when the NOTIFY arrived


def _targets(event: LiveEvent, by_org: dict[uuid.UUID, list[Connection]]) -> list[Connection]:
    if event.conversation_id is None and event.user_id is None and event.space_id is None:
        return []  # for nobody (cannot be sent: `publish_live` always names one)
    return [c for c in by_org.get(event.org_id, ()) if event.user_id in (None, c.user_id)]


async def deliver_batch(
    database: Database | None, connections: Sequence[Connection], batch: Sequence[Received]
) -> None:
    """Every event of `batch` to every stream of `connections` that may have it."""
    by_org: dict[uuid.UUID, list[Connection]] = defaultdict(list)
    for connection in connections:
        by_org[connection.org_id].append(connection)
    plan = [(item, targets) for item in batch if (targets := _targets(item.event, by_org))]
    if not plan or database is None:
        return
    pair_sessions: set[uuid.UUID] = set()
    person_sessions: set[uuid.UUID] = set()
    space_sessions: set[uuid.UUID] = set()
    conversation_ids: set[uuid.UUID] = set()
    space_ids: set[uuid.UUID] = set()
    for item, targets in plan:
        if item.event.for_space:
            assert item.event.space_id is not None
            space_ids.add(item.event.space_id)
            space_sessions.update(c.session_id for c in targets)
        elif item.event.conversation_id is None:
            person_sessions.update(c.session_id for c in targets)
        else:
            conversation_ids.add(item.event.conversation_id)
            pair_sessions.update(c.session_id for c in targets)
    try:
        async with database.session_factory() as session:
            pairs = await receiving_pairs(session, pair_sessions, conversation_ids)
            valid = await valid_sessions(session, person_sessions)
            readers = await space_readers(session, space_sessions, space_ids)
    except Exception as exc:
        logger.warning("live.check_failed", extra={"error": type(exc).__name__})
        LIVE_RESYNCS.labels(reason="check_failed").inc()
        for connection in {c for _, targets in plan for c in targets}:
            connection.push(RESYNC)
        return
    for item, targets in plan:
        event = item.event
        frame = event.frame()
        for connection in targets:
            if _may_have(event, connection, pairs, valid, readers):
                connection.push(frame)
        LIVE_DELIVERY_LAG.observe(time.monotonic() - item.at)


def _may_have(
    event: LiveEvent,
    connection: Connection,
    pairs: set[tuple[uuid.UUID, uuid.UUID]],
    valid: set[uuid.UUID],
    readers: set[tuple[uuid.UUID, uuid.UUID]],
) -> bool:
    if event.for_space:
        return (connection.session_id, event.space_id) in readers
    if event.conversation_id is not None:
        return (connection.session_id, event.conversation_id) in pairs
    return connection.session_id in valid
