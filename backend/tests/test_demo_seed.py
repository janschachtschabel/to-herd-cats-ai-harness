"""The demo data (scripts/demo_seed.py): people, a team space with pages, channels with
messages, thread replies, mentions and reactions, a direct message, and a page
discussion that starts with the worker's system entries.

The script talks to the public API as the browser does; here to the test app. The
worker's handlers run in the test's transaction (`settle`), as in test_page_threads.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.notifications import notify_on_message
from app.modules.messaging.threads import page_timeline
from app.modules.users.models import User
from app.modules.wiki.events import PAGE_EVENTS
from scripts.demo_seed import DemoExists, DemoFailed, main, seed
from tests.factories import PASSWORD, login

DEMO_PASSWORD = "demo-password-123"


async def _handle(session: AsyncSession) -> None:
    """What the worker would do with the events so far (again, where it already did)."""
    rows = await session.scalars(select(EventOutbox).order_by(EventOutbox.id))
    for row in rows.all():
        if row.type in PAGE_EVENTS:
            await page_timeline(session, Event.of(row))
        elif row.type == "message.created":
            await notify_on_message(session, Event.of(row))


async def _get(client: AsyncClient, path: str, **params: Any) -> Any:
    response = await client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def _top(client: AsyncClient, conversation_id: str) -> list[dict[str, Any]]:
    page = await _get(client, f"/api/conversations/{conversation_id}/messages", limit=100)
    return list(reversed(page["items"]))  # oldest first


@pytest.fixture
async def demo(
    session: AsyncSession,
    make_client: Callable[..., Awaitable[AsyncClient]],
    owner_user: User,
) -> dict[str, Any]:
    async def connect() -> AsyncClient:
        return await make_client(csrf=True)

    seeded = await seed(
        connect,
        admin_email=owner_user.email,
        admin_password=PASSWORD,
        people_password=DEMO_PASSWORD,
        settle=lambda: _handle(session),
        wait_seconds=0,
    )
    await _handle(session)
    clients = {}
    for key, email in seeded.emails.items():
        clients[key] = await make_client(csrf=True)
        await login(clients[key], email, DEMO_PASSWORD)
    return {"seeded": seeded, "clients": clients, "connect": connect, "owner": owner_user}


async def test_channels_hold_messages_threads_mentions_and_reactions(demo: dict[str, Any]) -> None:
    seeded, clara = demo["seeded"], demo["clients"]["clara"]
    channels = await _get(clara, f"/api/spaces/{seeded.space_id}/channels")
    assert [c["name"] for c in channels["items"]] == ["projekt-kranich", "team-nord"]
    by_name = {c["name"]: c["id"] for c in channels["items"]}

    team = await _top(clara, by_name["team-nord"])
    assert [m["author"]["name"] for m in team] == ["Anna Nord", "Ben Berg"]
    reactions = {r["emoji"]: r["count"] for r in team[0]["reactions"]}
    assert reactions == {"👍": 1, "🎉": 1}
    assert team[1]["mentions"] == [str(seeded.ids["clara"])]

    kranich = await _top(clara, by_name["projekt-kranich"])
    assert kranich[0]["mentions"] == [str(seeded.ids["ben"])]
    assert kranich[0]["reply_count"] == 2
    replies = await _get(clara, f"/api/messages/{kranich[0]['id']}/replies")
    assert [m["author"]["name"] for m in replies["items"]] == ["Ben Berg", "Clara Klein"]


async def test_the_mentioned_and_the_thread_starter_have_activity(demo: dict[str, Any]) -> None:
    clients = demo["clients"]
    reasons = {}
    for key in ("anna", "ben", "clara"):
        items = (await _get(clients[key], "/api/activity"))["items"]
        reasons[key] = sorted(entry["reason"] for entry in items)
    # Ben and Clara were mentioned in channels, Anna in the page discussion. Anna
    # started the Kranich thread (replies by Ben and Clara); Ben replied there before
    # Clara, and Anna answered his question in the page discussion.
    assert reasons == {
        "anna": ["mention", "reply", "reply"],
        "ben": ["mention", "reply", "reply"],
        "clara": ["mention"],
    }


async def test_a_direct_message_between_anna_and_ben(demo: dict[str, Any]) -> None:
    clients = demo["clients"]
    dms = (await _get(clients["ben"], "/api/dms"))["items"]
    assert len(dms) == 1
    names = sorted(p["name"] for p in dms[0]["participants"])
    assert names == ["Anna Nord", "Ben Berg"]
    assert [m["author"]["name"] for m in await _top(clients["ben"], dms[0]["id"])] == [
        "Anna Nord",
        "Ben Berg",
    ]
    assert (await _get(clients["clara"], "/api/dms"))["items"] == []


async def test_the_page_discussion_starts_with_system_entries(demo: dict[str, Any]) -> None:
    seeded, clara = demo["seeded"], demo["clients"]["clara"]
    thread = await _get(clara, f"/api/pages/{seeded.page_id}/thread")
    items = await _top(clara, thread["id"])
    kinds = [
        json.loads(m["body_md"])["key"] if m["kind"] == "system" else m["author"]["name"]
        for m in items
    ]
    assert kinds == [
        "page.created",
        "page.published",
        "page.version_restored",
        "Ben Berg",
    ]
    assert items[-1]["mentions"] == [str(seeded.ids["anna"])]
    assert items[-1]["reply_count"] == 1


async def test_a_second_run_stops_before_changing_anything(demo: dict[str, Any]) -> None:
    async def nothing() -> None:
        raise AssertionError("must not get this far")

    with pytest.raises(DemoExists):
        await seed(
            demo["connect"],
            admin_email=demo["owner"].email,
            admin_password=PASSWORD,
            people_password=DEMO_PASSWORD,
            settle=nothing,
            wait_seconds=0,
        )


async def test_without_a_worker_the_demo_says_so(
    make_client: Callable[..., Awaitable[AsyncClient]], owner_user: User
) -> None:
    async def connect() -> AsyncClient:
        return await make_client(csrf=True)

    async def no_worker() -> None:
        return None

    with pytest.raises(DemoFailed, match="is the worker running"):
        await seed(
            connect,
            admin_email=owner_user.email,
            admin_password=PASSWORD,
            people_password=DEMO_PASSWORD,
            settle=no_worker,
            wait_seconds=0,
        )


def test_passwords_come_only_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("HERD_DEMO_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("HERD_DEMO_PASSWORD", "short")
    assert main(["--admin", "admin@example.com"]) == 2
    assert "HERD_DEMO_PASSWORD" in capsys.readouterr().out
