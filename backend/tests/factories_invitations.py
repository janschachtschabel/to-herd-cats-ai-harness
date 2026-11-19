"""Invitations for tests (plan M10 task 4): a team with a calendar, setting an event's
attendees, answering, reading the attendee list, running the calendar's notification
handlers over every event so far (as the worker would, again where it had them), and
reading a person's calendar notifications."""

from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event, EventOutbox
from app.modules.calendars.notifications import on_invited, on_responded
from app.modules.messaging.notification_models import Notification
from app.modules.spaces.models import Space
from app.modules.users.models import User
from tests.factories import MakeUser
from tests.factories_calendar import logged_in, new_calendar
from tests.factories_spaces import MakeSpace

SPAN = ("2026-11-16T00:00:00Z", "2026-12-21T00:00:00Z")


def person(user: User, role: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"type": "user", "id": str(user.id)}
    return entry if role is None else {**entry, "role": role}


async def put_attendees(
    client: AsyncClient, event: dict[str, Any], attendees: list[dict[str, Any]], version: int
) -> Response:
    body = {"version": version, "attendees": attendees}
    return await client.put(f"/api/events/{event['id']}/attendees", json=body)


async def invite(
    client: AsyncClient, event: dict[str, Any], *attendees: dict[str, Any]
) -> dict[str, Any]:
    """Sets the event's attendees at its current version; the event as read after."""
    current = (await client.get(f"/api/events/{event['id']}")).json()
    r = await put_attendees(client, event, list(attendees), current["version"])
    assert r.status_code == 200, r.text
    after: dict[str, Any] = (await client.get(f"/api/events/{event['id']}")).json()
    return after


async def answer(client: AsyncClient, event_id: object, response: str) -> Response:
    """Answers at the version the caller reads now (0 when she sees no event)."""
    read = await client.get(f"/api/events/{event_id}")
    version = read.json()["version"] if read.status_code == 200 else 0
    return await client.post(
        f"/api/events/{event_id}/response", json={"response": response, "version": version}
    )


async def attendees(client: AsyncClient, event_id: object) -> list[dict[str, Any]]:
    r = await client.get(f"/api/events/{event_id}/attendees", params={"limit": 100})
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


def responses(items: list[dict[str, Any]]) -> dict[str, str]:
    """Each attendee's answer, by user id or address."""
    return {item["principal_id"] or item["email"]: item["response"] for item in items}


async def calendar_handlers(session: AsyncSession, *, again: bool = False) -> None:
    """The invitation and answer events not delivered yet through the notification
    handlers, as the worker would (`again`: every one so far, a redelivery)."""
    delivered: set[object] = session.info.setdefault("calendar_handlers_delivered", set())
    rows = [
        row
        for row in await session.scalars(
            select(EventOutbox)
            .where(EventOutbox.type.in_(("calendar_event.invited", "calendar_event.responded")))
            .order_by(EventOutbox.created_at, EventOutbox.id)
        )
        if again or row.id not in delivered
    ]
    delivered.update(row.id for row in rows)
    for row in rows:
        handle = on_invited if row.type == "calendar_event.invited" else on_responded
        await handle(session, Event.of(row))


async def notes(session: AsyncSession, user: User) -> list[Notification]:
    """The person's notifications about events, oldest first."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id, Notification.calendar_event_id.is_not(None))
        .order_by(Notification.created_at, Notification.id)
        .execution_options(populate_existing=True)
    )
    return list((await session.scalars(stmt)).all())


@dataclass
class Team:
    """A team space with a calendar: its organiser (moderator), a writer (editor) and
    a reader (viewer), and an outsider who is in none of it."""

    space: Space
    calendar: dict[str, Any]
    organiser: User
    writer: User
    reader: User
    outsider: User
    organiser_client: AsyncClient
    writer_client: AsyncClient
    reader_client: AsyncClient
    outsider_client: AsyncClient


async def team(make_client: Any, make_user: MakeUser, make_space: MakeSpace) -> Team:
    organiser, writer, reader, outsider = [await make_user() for _ in range(4)]
    space = await make_space(
        "team", members=[(organiser, "moderator"), (writer, "editor"), (reader, "viewer")]
    )
    organiser_client = await logged_in(make_client, organiser)
    return Team(
        space=space,
        calendar=await new_calendar(organiser_client, space.id, "Team"),
        organiser=organiser,
        writer=writer,
        reader=reader,
        outsider=outsider,
        organiser_client=organiser_client,
        writer_client=await logged_in(make_client, writer),
        reader_client=await logged_in(make_client, reader),
        outsider_client=await logged_in(make_client, outsider),
    )
