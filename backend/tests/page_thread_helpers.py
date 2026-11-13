"""Helpers for the page-thread tests: the timeline handler run over every wiki event so
far (as the worker would, again where it had them), a page's thread and its messages."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.threads import page_timeline
from app.modules.wiki.events import PAGE_EVENTS


async def timeline(session: AsyncSession) -> None:
    """Hand every wiki event so far to the handler (again, if it had them)."""
    rows = await session.scalars(
        select(EventOutbox).where(EventOutbox.type.in_(PAGE_EVENTS)).order_by(EventOutbox.id)
    )
    for row in rows.all():
        await page_timeline(session, Event.of(row))


async def thread_of(client: AsyncClient, page: dict[str, Any]) -> dict[str, Any]:
    response = await client.get(f"/api/pages/{page['id']}/thread")
    assert response.status_code == 200, response.text
    thread: dict[str, Any] = response.json()
    return thread


async def messages(client: AsyncClient, conversation_id: str, **params: Any) -> list[Any]:
    response = await client.get(f"/api/conversations/{conversation_id}/messages", params=params)
    assert response.status_code == 200, response.text
    return list(reversed(response.json()["items"]))  # oldest first


def keys(items: list[dict[str, Any]]) -> list[str]:
    return [m["system"]["key"] for m in items if m["kind"] == "system"]


async def events_of(session: AsyncSession, *types: str) -> list[str]:
    rows = await session.scalars(
        select(EventOutbox.type).where(EventOutbox.type.in_(types)).order_by(EventOutbox.id)
    )
    return list(rows)
