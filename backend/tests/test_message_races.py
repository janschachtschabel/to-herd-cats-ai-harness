"""Message writes that race, over separate connections with real commits
(tests/real_db.py): the parent's row lock keeps the reply counter right, and the
client's key makes a doubled send one message."""

import asyncio
import uuid

from httpx import AsyncClient
from sqlalchemy import func, select

from app.modules.messaging.models import Message
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

N = 8


async def _channel(make_real_client: MakeRealClient, real_db: RealDb) -> tuple[AsyncClient, str]:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space = (await owner.post("/api/spaces", json={"name": "Race", "kind": "team"})).json()
    channel = await owner.post(f"/api/spaces/{space['id']}/channels", json={"name": "rennen"})
    assert channel.status_code == 201, channel.text
    return owner, channel.json()["id"]


async def test_parallel_replies_are_all_counted(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, channel_id = await _channel(make_real_client, real_db)
    path = f"/api/conversations/{channel_id}/messages"
    parent = (await owner.post(path, json={"body_md": "Frage"})).json()
    responses = await asyncio.gather(
        *(
            owner.post(path, json={"body_md": f"Antwort {i}", "parent_id": parent["id"]})
            for i in range(N)
        )
    )
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    top = (await owner.get(path)).json()["items"]
    assert [(m["id"], m["reply_count"]) for m in top] == [(parent["id"], N)]
    latest = max(r.json()["created_at"] for r in responses)
    assert top[0]["last_reply_at"] == latest


async def test_a_doubled_send_is_one_message(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, channel_id = await _channel(make_real_client, real_db)
    path = f"/api/conversations/{channel_id}/messages"
    parent = (await owner.post(path, json={"body_md": "Frage"})).json()
    client_id = str(uuid.uuid4())
    body = {"body_md": "einmal", "client_id": client_id, "parent_id": parent["id"]}
    responses = await asyncio.gather(*(owner.post(path, json=body) for _ in range(N)))
    assert sorted(r.status_code for r in responses) == [200] * (N - 1) + [201]
    assert len({r.json()["id"] for r in responses}) == 1
    async with real_db.database.session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(Message).where(Message.parent_id == parent["id"])
        )
    assert count == 1
    top = (await owner.get(path)).json()["items"]
    assert top[0]["reply_count"] == 1
