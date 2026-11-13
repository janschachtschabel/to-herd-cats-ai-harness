"""One open stream of the live hub (`live.py`): a bounded queue of frames ready to
send. A client that falls QUEUE_SIZE frames behind gets its queue emptied and one
`resync` instead; a closed stream gets `None` and ends. Frames waiting together are
written together. Frames are bytes: `event:
<name>` + `data: {ids}`, or a comment line as heartbeat every HEARTBEAT_SECONDS."""

import asyncio
import uuid
from collections.abc import AsyncIterator

from app.modules.messaging.live_events import sse_frame

HEARTBEAT_SECONDS = 15.0
QUEUE_SIZE = 100
RETRY_MS = 5000  # how long a browser waits before it connects again

OPENING = f"retry: {RETRY_MS}\n\n".encode()
HEARTBEAT = b": ping\n\n"
RESYNC = sse_frame("resync", {})


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
            # Whatever else is queued goes out in the same write: a busy process
            # sends one chunk per batch, not one per event.
            chunk = [frame]
            while not self.queue.empty():
                more = self.queue.get_nowait()
                if more is None:
                    yield b"".join(chunk)
                    return
                chunk.append(more)
            yield b"".join(chunk)
