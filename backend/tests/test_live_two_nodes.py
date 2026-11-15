"""Review focus 3: a message written through one API process arrives on a stream held
by a second, separate API process. Two real processes (`python -m app.launch`) on a
scratch database and free ports: node A in role `all` (it migrates and runs the
worker), node B in role `api`. Both stop on SIGTERM while a stream is still open."""

import asyncio
import os
import signal
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from pathlib import Path

import asyncpg
import httpx
import pytest
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.listen import asyncpg_dsn
from tests.factories import PASSWORD
from tests.live_helpers import Stream, free_port, open_stream

BACKEND = Path(__file__).resolve().parent.parent
OWNER = "owner@nodes.example"
START_SECONDS = 60.0


@pytest.fixture
async def scratch_url() -> AsyncIterator[str]:
    """A database of its own (never herd_test), dropped afterwards."""
    admin = make_url(get_settings().test_database_url)
    name = f"herd_live_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    connection = await asyncpg.connect(asyncpg_dsn(admin))
    try:
        await connection.execute(f'CREATE DATABASE "{name}"')
        yield admin.set(database=name).render_as_string(hide_password=False)
    finally:
        await connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await connection.close()


class Node:
    def __init__(self, role: str, database_url: str, data_dir: Path) -> None:
        self.public, self.internal = free_port(), free_port()
        env = {
            **os.environ,
            "HERD_ROLE": role,
            "HERD_ENVIRONMENT": "development",
            "HERD_DATABASE_URL": database_url,
            "HERD_PUBLIC_PORT": str(self.public),
            "HERD_INTERNAL_PORT": str(self.internal),
            "HERD_BOOTSTRAP_ADMIN_EMAIL": OWNER,
            "HERD_BOOTSTRAP_ADMIN_PASSWORD": PASSWORD,
            "HERD_DATA_DIR": str(data_dir),
            "HERD_LOG_FORMAT": "text",
            "HERD_LOG_LEVEL": "WARNING",
        }
        env.pop("HERD_INTERNAL_TOKEN", None)  # no collab process
        self.process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "app.launch"], cwd=BACKEND, env=env
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.public}"

    async def ready(self) -> None:
        async with httpx.AsyncClient(trust_env=False) as probe:
            async with asyncio.timeout(START_SECONDS):
                while True:
                    assert self.process.poll() is None, "the node ended"
                    try:
                        answer = await probe.get(f"http://127.0.0.1:{self.internal}/ready")
                        if answer.status_code == 200:
                            return
                    except httpx.TransportError:
                        pass
                    await asyncio.sleep(0.2)

    async def stop(self) -> int:
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(loop.run_in_executor(None, self.process.wait), 20)


@contextmanager
def killed_at_exit(nodes: list[Node]) -> Iterator[None]:
    try:
        yield
    finally:
        for node in nodes:
            if node.process.poll() is None:
                node.process.kill()
                node.process.wait()


async def _client(node: Node) -> httpx.AsyncClient:
    client = httpx.AsyncClient(
        base_url=node.url, headers={"X-Requested-With": "herd"}, trust_env=False
    )
    answer = await client.post("/api/auth/login", json={"email": OWNER, "password": PASSWORD})
    assert answer.status_code == 200, answer.text
    return client


async def test_message_on_node_a_arrives_on_node_b(scratch_url: str, tmp_path: Path) -> None:
    nodes: list[Node] = []
    with killed_at_exit(nodes):
        nodes.append(Node("all", scratch_url, tmp_path / "a"))  # migrates, runs the worker
        await nodes[0].ready()
        nodes.append(Node("api", scratch_url, tmp_path / "b"))
        await nodes[1].ready()
        a, b = await _client(nodes[0]), await _client(nodes[1])
        me = (await b.get("/api/auth/me")).json()
        space = (await a.post("/api/spaces", json={"name": "Team", "kind": "team"})).json()
        channel = (await a.post(f"/api/spaces/{space['id']}/channels", json={"name": "k"})).json()
        stream: Stream = await open_stream(b, None, me["org"]["id"], me["user"]["id"])  # type: ignore[arg-type]
        sent = await a.post(
            f"/api/conversations/{channel['id']}/messages", json={"body_md": "von A"}
        )
        assert sent.status_code == 201, sent.text
        event = await stream.until_event("message.created", seconds=20)
        assert event.data == {
            "conversation_id": channel["id"],
            "message_id": sent.json()["id"],
            "parent_id": None,
        }
        # SIGTERM with the stream still open: node B ends it and stops in time.
        assert await nodes[1].stop() == 0
        await asyncio.wait_for(stream.ended.wait(), timeout=5)
        assert await nodes[0].stop() == 0
        await stream.close()
        await a.aclose()
        await b.aclose()
