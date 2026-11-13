"""Helpers for the live-delivery tests: the public app served by a real uvicorn on a
free port (httpx's ASGI transport cannot stream an endless response), a reader of
server-sent events, and a barrier that proves the hub has handled everything before.

The barrier (`Stream.settle`) is a NOTIFY of `activity.changed` for the stream's own
person: Postgres hands notifications to a listener in commit order and the hub handles
them one after the other, so once the barrier arrives every earlier event has been
handled; whatever this stream was going to get of them has arrived before it.
"""

import asyncio
import json
import socket
from dataclasses import dataclass, field
from typing import Any

import asyncpg
import httpx
import uvicorn
from fastapi import FastAPI

from app.core.db import Database
from app.core.listen import asyncpg_dsn
from app.launch import _Server
from app.modules.messaging.live import LiveHub
from app.modules.messaging.live_events import LIVE_CHANNEL
from app.worker.dispatcher import Dispatcher
from tests.factories import CSRF, login

WAIT = 10.0


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


async def until(predicate: Any, seconds: float = WAIT) -> None:  # noqa: ASYNC109
    async with asyncio.timeout(seconds):
        while not predicate():  # noqa: ASYNC110 -- waits on another task's state
            await asyncio.sleep(0.02)


@dataclass
class LiveServer:
    app: FastAPI
    port: int = field(default_factory=free_port)
    server: uvicorn.Server | None = None
    task: asyncio.Task[None] | None = None

    @property
    def hub(self) -> LiveHub:
        hub: LiveHub = self.app.state.live
        return hub

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def start(self) -> None:
        config = uvicorn.Config(
            self.app, host="127.0.0.1", port=self.port, log_config=None, access_log=False
        )
        self.server = _Server(config, before_shutdown=self.hub.close_all)
        self.task = asyncio.create_task(self.server.serve())
        await until(lambda: self.server is not None and self.server.started)
        await until(lambda: self.hub.listening)

    async def stop(self) -> None:
        if self.server is not None and self.task is not None:
            self.server.should_exit = True
            await asyncio.wait_for(self.task, timeout=WAIT)

    async def client(self, email: str | None = None) -> httpx.AsyncClient:
        client = httpx.AsyncClient(base_url=self.base_url, headers=CSRF, trust_env=False)
        if email is not None:
            await login(client, email)
        return client


@dataclass
class SseEvent:
    name: str
    data: dict[str, Any]


class Stream:
    """An open `GET /api/stream`, read in the background."""

    def __init__(self, response: httpx.Response, database: Database, org_id: Any, user_id: Any):
        self.response = response
        self.database = database
        self.org_id, self.user_id = org_id, user_id
        self.events: asyncio.Queue[SseEvent] = asyncio.Queue()
        self.raw: list[str] = []
        self.comments: list[str] = []
        self.retry: list[str] = []
        self.ended = asyncio.Event()
        self._reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        name, data = "message", ""
        try:
            async for line in self.response.aiter_lines():
                self.raw.append(line)
                if line == "":
                    if data:
                        self.events.put_nowait(SseEvent(name, json.loads(data)))
                    name, data = "message", ""
                elif line.startswith(":"):
                    self.comments.append(line)
                elif line.startswith("event: "):
                    name = line.removeprefix("event: ")
                elif line.startswith("data: "):
                    data = line.removeprefix("data: ")
                elif line.startswith("retry: "):
                    self.retry.append(line.removeprefix("retry: "))
        except (httpx.ReadError, httpx.RemoteProtocolError):
            pass
        finally:
            self.ended.set()

    async def next(self, seconds: float = WAIT) -> SseEvent:  # noqa: ASYNC109
        return await asyncio.wait_for(self.events.get(), timeout=seconds)

    async def until_event(self, name: str, seconds: float = WAIT) -> SseEvent:  # noqa: ASYNC109
        """The next event called `name`, skipping others."""
        async with asyncio.timeout(seconds):
            while True:
                event = await self.events.get()
                if event.name == name:
                    return event

    async def barrier(self) -> None:
        await notify(
            self.database,
            {
                "t": "activity.changed",
                "o": str(self.org_id),
                "c": None,
                "m": None,
                "p": None,
                "u": str(self.user_id),
            },
        )

    async def settle(self) -> None:
        """Skip everything until the hub has handled all that came before."""
        await self.barrier()
        await self.until_event("activity.changed")

    async def expect_nothing(self) -> None:
        """Nothing arrived since the last settle: the next event is the barrier."""
        await self.barrier()
        event = await self.next()
        assert event.name == "activity.changed", event
        assert event.data == {"conversation_id": None, "message_id": None, "parent_id": None}

    async def close(self) -> None:
        await self.response.aclose()
        self._reader.cancel()
        await asyncio.gather(self._reader, return_exceptions=True)


async def open_stream(
    client: httpx.AsyncClient, database: Database, org_id: Any, user_id: Any
) -> Stream:
    response = await client.send(client.build_request("GET", "/api/stream"), stream=True)
    assert response.status_code == 200, (await response.aread()).decode()
    return Stream(response, database, org_id, user_id)


async def notify(database: Database, payload: dict[str, Any]) -> None:
    connection = await asyncpg.connect(asyncpg_dsn(database.engine.url))
    try:
        await connection.execute("SELECT pg_notify($1, $2)", LIVE_CHANNEL, json.dumps(payload))
    finally:
        await connection.close()


async def drain(database: Database) -> None:
    """Every pending outbox event through every registered handler (the worker)."""
    import app.worker.handlers  # noqa: F401, PLC0415 -- registers publish_live

    await Dispatcher(database).drain()
