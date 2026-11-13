"""The notification handler under the real dispatcher, with real commits (review
focus 2): however often and however concurrently a message event is handled, a
mention leaves exactly one notification and one `notification.created`.

The handler is registered twice under different names, so each event is handled
twice with separate delivery records: only the unique key keeps the effect single.
Two dispatchers drain the same events at the same time on top of that."""

import asyncio
import subprocess
import sys
from pathlib import Path

from sqlalchemy import func, select

from app.core.outbox import EventOutbox
from app.modules.messaging.notification_models import Notification
from app.modules.messaging.notifications import notify_on_message
from app.worker.dispatcher import Dispatcher
from app.worker.registry import HandlerRegistry
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

BACKEND = Path(__file__).resolve().parent.parent
N = 5


def _twice() -> HandlerRegistry:
    registry = HandlerRegistry()
    for name in ("notify_a", "notify_b"):
        registry.handler(("message.created", "message.updated"), name)(notify_on_message)
    return registry


async def test_handled_twice_at_once_one_notification_each(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, member = await make_real_client(), await make_real_client()
    await login(owner, real_db.owner_email)
    member_id = (await login(member, real_db.member_email))["user"]["id"]
    space = (await owner.post("/api/spaces", json={"name": "Team", "kind": "team"})).json()
    added = await owner.put(
        f"/api/spaces/{space['id']}/members",
        json={"member_type": "user", "member_id": member_id, "role": "viewer"},
    )
    assert added.status_code in (200, 201, 204), added.text
    channel = (await owner.post(f"/api/spaces/{space['id']}/channels", json={"name": "k"})).json()
    for i in range(N):
        sent = await owner.post(
            f"/api/conversations/{channel['id']}/messages",
            json={"body_md": f"@member {i}", "mentions": [member_id]},
        )
        assert sent.status_code == 201, sent.text
    dispatchers = [Dispatcher(real_db.database, _twice(), batch_size=2) for _ in range(2)]
    await asyncio.gather(*(d.drain() for d in dispatchers))
    async with real_db.database.session_factory() as session:
        notifications = await session.scalar(select(func.count()).select_from(Notification))
        created = await session.scalar(
            select(func.count())
            .select_from(EventOutbox)
            .where(EventOutbox.type == "notification.created")
        )
    assert (notifications, created) == (N, N)
    page = (await member.get("/api/activity", params={"limit": 100})).json()
    assert len(page["items"]) == N


def test_the_worker_registers_the_notification_handler() -> None:
    """A fresh process that imports only the worker has the handler."""
    probe = (
        "import app.worker.main\n"
        "from app.worker.registry import REGISTRY\n"
        "print(sorted(h.name for h in REGISTRY.for_type('message.created')))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=BACKEND, capture_output=True, text=True, check=True
    )
    assert "notify_on_message" in result.stdout
