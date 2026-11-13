"""Page threads under real commits: one thread per page however many ask at once, and
one system message per event however often and however concurrently the timeline
handler gets it (review focus 2)."""

import asyncio

from sqlalchemy import func, select

from app.modules.messaging.models import Conversation, Message, MessageKind
from app.modules.messaging.threads import page_timeline
from app.modules.wiki.events import PAGE_EVENTS
from app.worker.dispatcher import Dispatcher
from app.worker.registry import HandlerRegistry
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb


async def test_one_thread_per_page_when_many_ask_at_once(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space = (await owner.post("/api/spaces", json={"name": "T", "kind": "team"})).json()
    page = (await owner.post(f"/api/spaces/{space['id']}/pages", json={"title": "S"})).json()
    clients = [await make_real_client() for _ in range(8)]
    for client in clients:
        await login(client, real_db.owner_email)
    answers = await asyncio.gather(*(c.get(f"/api/pages/{page['id']}/thread") for c in clients))
    assert {a.status_code for a in answers} == {200}
    assert len({a.json()["id"] for a in answers}) == 1
    async with real_db.database.session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(Conversation).where(Conversation.page_id == page["id"])
        )
    assert count == 1


async def test_the_timeline_writes_each_event_once(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space = (await owner.post("/api/spaces", json={"name": "T", "kind": "team"})).json()
    for i in range(4):
        page = (
            await owner.post(f"/api/spaces/{space['id']}/pages", json={"title": f"S{i}"})
        ).json()
        published = await owner.post(
            f"/api/pages/{page['id']}/publish", json={"version": page["version"]}
        )
        assert published.status_code == 200
    registry = HandlerRegistry()
    for name in ("timeline_a", "timeline_b"):
        registry.handler(PAGE_EVENTS, name)(page_timeline)
    dispatchers = [Dispatcher(real_db.database, registry, batch_size=2) for _ in range(2)]
    await asyncio.gather(*(d.drain() for d in dispatchers))
    async with real_db.database.session_factory() as session:
        system = await session.scalar(
            select(func.count()).select_from(Message).where(Message.kind == MessageKind.SYSTEM)
        )
        threads = await session.scalar(
            select(func.count()).select_from(Conversation).where(Conversation.page_id.is_not(None))
        )
    assert (system, threads) == (8, 4)  # created and published, for each of four pages
