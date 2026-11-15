"""The live hub of one API process (spec 6.4, plan M3 task 7): it listens on
`herd_live` over a connection of its own, outside the pool (`core/listen.py`), and
hands each event to the open streams (`GET /api/stream`) that may have it.

- The hub works in batches (`live_batch.py`): it takes whatever has arrived (at most
  BATCH_SIZE events) and decides who may get them in at most two statements for the
  whole batch: the login session is still valid, the person is active, and either it
  is the person the event names or the person may see the conversation now. Nothing
  is remembered between batches, so a membership removed while a stream is open
  stops the next batch already.
- Falling behind is bounded: when the oldest event waiting is older than
  `max_lag_seconds` (HERD_LIVE_MAX_LAG_SECONDS, default 5), the hub drops everything
  waiting and sends every stream `resync` (the clients reload what they show) instead
  of delivering ever later. Gauge `herd_live_queue_depth`, histogram
  `herd_live_delivery_lag_seconds`, counter `herd_live_resyncs_total{reason}`.
- Every SESSION_CHECK_SECONDS one query finds the streams whose session has ended
  (logout, expiry, deactivation); they are closed.
- A stream holds no database connection: the hub borrows one from the pool for each
  batch and each check and gives it back at once.
- A stream's queue holds QUEUE_SIZE frames (`live_connection.py`); a client that falls
  further behind gets its queue emptied and one `resync` instead. After the LISTEN
  connection was lost and is back, every stream gets `resync` (what was sent
  meanwhile is lost); so does every stream a batch was for whose check failed.
- At most MAX_STREAMS_PER_SESSION streams per login session and
  MAX_STREAMS_PER_PERSON per person (whatever the sessions) in this process; the next
  is refused (429).
"""

import asyncio
import logging
import time
import uuid
from collections import Counter
from contextlib import suppress

from app.core.db import Database
from app.core.errors import AppError, RateLimited
from app.core.listen import Listener
from app.modules.messaging.live_batch import BATCH_SIZE, Received, deliver_batch
from app.modules.messaging.live_connection import RESYNC, Connection
from app.modules.messaging.live_events import LIVE_CHANNEL, LiveEvent, decode
from app.modules.messaging.live_repository import valid_sessions
from app.modules.messaging.metrics import (
    LIVE_EVENTS,
    LIVE_QUEUE_DEPTH,
    LIVE_RESYNCS,
    SSE_CONNECTIONS,
)

logger = logging.getLogger(__name__)

SESSION_CHECK_SECONDS = 30.0
MAX_STREAMS_PER_SESSION = 5
MAX_STREAMS_PER_PERSON = 10
MAX_LAG_SECONDS = 5.0  # default of HERD_LIVE_MAX_LAG_SECONDS
INCOMING_LIMIT = 10_000  # notifications waiting for the hub; more means resync for all


class TooManyStreams(RateLimited):
    code = "live.too_many_streams"


class LiveUnavailable(AppError):
    status_code = 503
    code = "live.unavailable"


class LiveHub:
    def __init__(self, max_lag_seconds: float = MAX_LAG_SECONDS) -> None:
        self.database: Database | None = None
        self.max_lag_seconds = max_lag_seconds
        self._streams: dict[uuid.UUID, list[Connection]] = {}  # by login session
        self._per_person: Counter[uuid.UUID] = Counter()  # open streams by person
        # (payload, time.monotonic() of arrival)
        self._incoming: asyncio.Queue[tuple[str, float]] = asyncio.Queue(maxsize=INCOMING_LIMIT)
        self._overflowed = False
        self._listener: Listener | None = None
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def running(self) -> bool:
        return bool(self._tasks) and not self._stop.is_set()

    @property
    def listening(self) -> bool:
        return self._listener is not None and self._listener.connected

    def stream_count(self) -> int:
        return sum(len(streams) for streams in self._streams.values())

    async def start(self, database: Database) -> None:
        self.database = database
        self._stop.clear()
        self._listener = Listener(
            database.engine.url, LIVE_CHANNEL, self._received, on_connect=self._reconnected
        )
        self._tasks = [
            asyncio.create_task(self._listener.run(self._stop)),
            asyncio.create_task(self._deliver_loop()),
            asyncio.create_task(self._check_loop()),
        ]

    async def stop(self) -> None:
        self._stop.set()
        self.close_all()
        for task in self._tasks[1:]:
            task.cancel()
        for task in self._tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._tasks = []

    def connect(self, org_id: uuid.UUID, user_id: uuid.UUID, session_id: uuid.UUID) -> Connection:
        streams = self._streams.get(session_id, [])
        if (
            len(streams) >= MAX_STREAMS_PER_SESSION
            or self._per_person[user_id] >= MAX_STREAMS_PER_PERSON
        ):
            raise TooManyStreams()
        connection = Connection(org_id, user_id, session_id)
        self._streams.setdefault(session_id, streams).append(connection)
        self._per_person[user_id] += 1
        SSE_CONNECTIONS.inc()
        return connection

    def disconnect(self, connection: Connection) -> None:
        connection.close()
        streams = self._streams.get(connection.session_id, [])
        if connection in streams:
            streams.remove(connection)
            self._per_person[connection.user_id] -= 1
            if not self._per_person[connection.user_id]:
                del self._per_person[connection.user_id]
            SSE_CONNECTIONS.dec()
        if not streams:
            self._streams.pop(connection.session_id, None)

    def close_all(self) -> None:
        """Every stream ends (the process stops; browsers connect to another one)."""
        for connection in self._all():
            connection.close()

    def resync_all(self) -> None:
        for connection in self._all():
            connection.push(RESYNC)

    def _reconnected(self) -> None:
        LIVE_RESYNCS.labels(reason="reconnect").inc()
        self.resync_all()

    def _all(self) -> list[Connection]:
        return [c for streams in self._streams.values() for c in streams]

    def _received(self, payload: str) -> None:
        try:
            self._incoming.put_nowait((payload, time.monotonic()))
        except asyncio.QueueFull:
            self._overflowed = True
        LIVE_QUEUE_DEPTH.set(self._incoming.qsize())

    async def _deliver_loop(self) -> None:
        while True:
            batch = [await self._incoming.get()]
            try:
                await self.handle(batch)
            except Exception as exc:  # the loop must outlive any one batch
                logger.warning("live.deliver_failed", extra={"error": type(exc).__name__})

    async def handle(self, batch: list[tuple[str, float]]) -> None:
        """`batch` and whatever else has arrived meanwhile (up to BATCH_SIZE)."""
        while len(batch) < BATCH_SIZE:
            try:
                batch.append(self._incoming.get_nowait())
            except asyncio.QueueEmpty:
                break
        LIVE_QUEUE_DEPTH.set(self._incoming.qsize())
        if self._overflowed:
            self._overflowed = False
            LIVE_RESYNCS.labels(reason="overflow").inc()
            self.resync_all()
        behind = time.monotonic() - batch[0][1]
        if behind > self.max_lag_seconds:
            dropped = len(batch) + self._drop_incoming()
            logger.warning(
                "live.fell_behind", extra={"dropped": dropped, "seconds": round(behind, 1)}
            )
            LIVE_RESYNCS.labels(reason="lag").inc()
            self.resync_all()
            return
        received: list[Received] = []
        for payload, at in batch:
            event = decode(payload)
            if event is None:
                logger.warning("live.payload_dropped")
                continue
            LIVE_EVENTS.labels(type=event.name).inc()
            received.append(Received(event, at))
        await deliver_batch(self.database, self._all(), received)

    def _drop_incoming(self) -> int:
        dropped = 0
        while True:
            try:
                self._incoming.get_nowait()
            except asyncio.QueueEmpty:
                break
            dropped += 1
        LIVE_QUEUE_DEPTH.set(0)
        return dropped

    async def deliver(self, event: LiveEvent) -> None:
        """One event on its own (as a batch of one)."""
        await deliver_batch(self.database, self._all(), [Received(event, time.monotonic())])

    async def check_sessions(self) -> None:
        """Close the streams whose login session has ended."""
        if not self._streams or self.database is None:
            return
        async with self.database.session_factory() as session:
            valid = await valid_sessions(session, set(self._streams))
        for connection in self._all():
            if connection.session_id not in valid:
                connection.close()

    async def _check_loop(self) -> None:
        while True:
            await asyncio.sleep(SESSION_CHECK_SECONDS)
            try:
                await self.check_sessions()
            except Exception as exc:
                logger.warning("live.session_check_failed", extra={"error": type(exc).__name__})
