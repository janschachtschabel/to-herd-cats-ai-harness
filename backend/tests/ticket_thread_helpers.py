"""Helpers for the ticket-thread tests: the ticket handlers and the message handler run
over every event so far (as the worker would, again where it had them), and a
ticket's thread."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.messaging.notifications import notify_on_message
from app.modules.tickets.events import TICKET_EVENTS
from app.modules.tickets.handlers import notify_on_ticket, ticket_timeline


async def ticket_handlers(session: AsyncSession, *, notify_first: bool = False) -> None:
    """Hand every ticket event so far to both ticket handlers (again, if they had
    them); with `notify_first`, the notification handler before the timeline."""
    rows = await session.scalars(
        select(EventOutbox).where(EventOutbox.type.in_(TICKET_EVENTS)).order_by(EventOutbox.id)
    )
    handlers = [ticket_timeline, notify_on_ticket]
    if notify_first:
        handlers.reverse()
    for row in rows.all():
        for handle in handlers:
            await handle(session, Event.of(row))


async def message_handlers(session: AsyncSession) -> None:
    """Hand every message event so far to `notify_on_message`."""
    rows = await session.scalars(
        select(EventOutbox)
        .where(EventOutbox.type.in_(("message.created", "message.updated")))
        .order_by(EventOutbox.id)
    )
    for row in rows.all():
        await notify_on_message(session, Event.of(row))


async def ticket_thread(client: AsyncClient, ticket: dict[str, Any]) -> dict[str, Any]:
    response = await client.get(f"/api/tickets/{ticket['number']}/thread")
    assert response.status_code == 200, response.text
    thread: dict[str, Any] = response.json()
    return thread
