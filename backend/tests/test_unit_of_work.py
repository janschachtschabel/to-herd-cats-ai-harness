"""The request's transaction commits before the response is sent (real get_session)."""

from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.modules.spaces.models import Space
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb


async def _space_count(real_db: RealDb, name: str) -> int:
    async with real_db.database.session_factory() as s:
        stmt = select(func.count()).select_from(Space).where(Space.name == name)
        return int(await s.scalar(stmt) or 0)


async def test_commit_happens_before_the_response_starts(
    real_db: RealDb, make_real_client: MakeRealClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = await make_real_client()
    await login(client, real_db.owner_email)
    events: list[str] = []
    original_commit = AsyncSession.commit

    async def recording_commit(self: AsyncSession) -> None:
        await original_commit(self)
        events.append("commit")

    def recording_app(app: ASGIApp) -> ASGIApp:
        async def wrapped(scope: Scope, receive: Receive, send: Send) -> None:
            async def recording_send(message: Message) -> None:
                if message["type"] == "http.response.start":
                    events.append(f"response {message['status']}")
                await send(message)

            await app(scope, receive, recording_send)

        return wrapped

    monkeypatch.setattr(AsyncSession, "commit", recording_commit)
    recorded = await make_real_client(wrap=recording_app)
    recorded.cookies = client.cookies
    response = await recorded.post("/api/spaces", json={"name": "Ordered", "kind": "team"})
    assert response.status_code == 201, response.text
    # Creating a space counts towards the write limit (R18-5), whose count commits at
    # once (J10, no lock held through the request); then the request's own transaction.
    assert events == ["commit", "commit", "response 201"]
    # Read-your-own-write: the next request sees the space.
    space_id = response.json()["id"]
    assert (await client.get(f"/api/spaces/{space_id}")).status_code == 200


async def test_failed_commit_answers_500_and_keeps_nothing(
    real_db: RealDb, make_real_client: MakeRealClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = await make_real_client()
    await login(client, real_db.owner_email)

    async def failing_commit(self: AsyncSession) -> Any:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)
    response = await client.post("/api/spaces", json={"name": "Lost", "kind": "team"})
    monkeypatch.undo()
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal"
    assert await _space_count(real_db, "Lost") == 0
