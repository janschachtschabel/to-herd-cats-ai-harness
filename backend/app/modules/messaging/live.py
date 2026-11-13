"""The live hub of one API process (spec 6.4, plan M3 task 7): it listens on
`herd_live` over a connection of its own, outside the pool (`core/listen.py`), and
hands each event to the open streams (`GET /api/stream`) that may have it.

- Who gets an event is decided per event, in one query for all streams of the
  event's organisation (`live_repository.receiving_sessions`): the login session is
  still valid, the person is active, and either it is the person the event names or
  the person may see the conversation now. Nothing is remembered between events, so
  a membership removed while a stream is open stops the next event already.
- Every SESSION_CHECK_SECONDS one query finds the streams whose session has ended
  (logout, expiry, deactivation); they are closed.
- A stream holds no database connection: the hub borrows one from the pool for each
  event and each check and gives it back at once.
- A stream's queue holds QUEUE_SIZE frames; a client that falls further behind gets
  its queue emptied and one `resync` instead. After the LISTEN connection was lost and
  is back, every stream gets `resync` (what was sent meanwhile is lost); so does every
  stream of an organisation whose event could not be checked (database error).
- At most MAX_STREAMS_PER_SESSION streams per login session in this process; the next
  is refused (429).

Frames are bytes ready to send: `event: <name>` + `data: {ids}`, or a comment line as
heartbeat every HEARTBEAT_SECONDS. A closed stream gets `None` and ends.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress

from app.core.db import Database
from app.core.errors import AppError, RateLimited
from app.core.listen import Listener
from app.modules.messaging.live_events import LIVE_CHANNEL, LiveEvent, decode, sse_frame
from app.modules.messaging.live_repository import receiving_sessions, valid_sessions
from app.modules.messaging.metrics import LIVE_EVENTS, SSE_CONNECTIONS

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 15.0
SESSION_CHECK_SECONDS = 30.0
QUEUE_SIZE = 100
MAX_STREAMS_PER_SESSION = 5
INCOMING_LIMIT = 10_000  # notifications waiting for the hub; more means resync for all
RETRY_MS = 5000  # how long a browser waits before it connects again

OPENING = f"retry: {RETRY_MS}\n\n".encode()
HEARTBEAT = b": ping\n\n"
RESYNC = sse_frame("resync", {})


class TooManyStreams(RateLimited):
    code = "live.too_many_streams"


class LiveUnavailable(AppError):
    status_code = 503
    code = "live.unavailable"


class Connection:
    """One open stream."""

    def __init__(self, org_id: uuid.UUID, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        self.org_id = org_id
        self.user_id = user_id
        self.session_id = session_id
        self.queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self.closed = False

    def push(self, frame: bytes) -> None:
        if self.closed:
            return
        try:
            self.queue.put_nowait(frame)
        except asyncio.QueueFull:
            self._empty()
            self.queue.put_nowait(RESYNC)

    def close(self) -> None:
        """End the stream; frames not yet sent are dropped."""
        if not self.closed:
            self.closed = True
            self._empty()
            self.queue.put_nowait(None)

    def _empty(self) -> None:
        while not self.queue.empty():
            self.queue.get_nowait()

    async def frames(self) -> AsyncIterator[bytes]:
        yield OPENING
        while True:
            try:
                frame = await asyncio.wait_for(self.queue.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield HEARTBEAT
                continue
            if frame is None:
                return
            yield frame


class LiveHub:
    def __init__(self) -> None:
        self.database: Database | None = None
        self._streams: dict[uuid.UUID, list[Connection]] = {}  # by login session
        self._incoming: asyncio.Queue[str] = asyncio.Queue(maxsize=INCOMING_LIMIT)
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
            database.engine.url, LIVE_CHANNEL, self._received, on_connect=self.resync_all
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
        streams = self._streams.setdefault(session_id, [])
        if len(streams) >= MAX_STREAMS_PER_SESSION:
            raise TooManyStreams()
        connection = Connection(org_id, user_id, session_id)
        streams.append(connection)
        SSE_CONNECTIONS.inc()
        return connection

    def disconnect(self, connection: Connection) -> None:
        connection.close()
        streams = self._streams.get(connection.session_id, [])
        if connection in streams:
            streams.remove(connection)
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

    def _all(self) -> list[Connection]:
        return [c for streams in self._streams.values() for c in streams]

    def _received(self, payload: str) -> None:
        try:
            self._incoming.put_nowait(payload)
        except asyncio.QueueFull:
            self._overflowed = True

    async def _deliver_loop(self) -> None:
        while True:
            payload = await self._incoming.get()
            if self._overflowed:
                self._overflowed = False
                self.resync_all()
            event = decode(payload)
            if event is None:
                logger.warning("live.payload_dropped")
                continue
            LIVE_EVENTS.labels(type=event.name).inc()
            try:
                await self.deliver(event)
            except Exception as exc:  # the loop must outlive any one event
                logger.warning("live.deliver_failed", extra={"error": type(exc).__name__})

    async def deliver(self, event: LiveEvent) -> None:
        """The event to every stream that may have it, after one query."""
        targets = [
            c
            for c in self._all()
            if c.org_id == event.org_id and event.user_id in (None, c.user_id)
        ]
        if not targets or self.database is None:
            return
        try:
            async with self.database.session_factory() as session:
                allowed = await receiving_sessions(
                    session,
                    event.org_id,
                    {c.session_id for c in targets},
                    conversation_id=event.conversation_id,
                    user_id=event.user_id,
                )
        except Exception as exc:
            logger.warning("live.check_failed", extra={"error": type(exc).__name__})
            for connection in targets:
                connection.push(RESYNC)
            return
        frame = event.frame()
        for connection in targets:
            if connection.session_id in allowed:
                connection.push(frame)

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
