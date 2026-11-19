"""What invitations tell (plan M10 task 4, decision 7): the activity view alone ("Für
mich"), never a channel or a direct message. `invitation` to each person invited, again
when the event's time changes (the others' answers go back to `needs_action`) and when
it is cancelled or deleted; `invite_reply` to the organiser when someone declines or
answers "maybe". One notification per person, event and reason, renewed by a further
change. Answering names the event's version read (409 after a change)."""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.models import Message
from app.modules.messaging.notification_models import Notification
from tests.factories import MakeUser
from tests.factories_calendar import new_event
from tests.factories_invitations import (
    answer,
    attendees,
    calendar_handlers,
    invite,
    notes,
    person,
    responses,
    team,
)
from tests.factories_spaces import MakeSpace


async def _move(client: AsyncClient, event: dict[str, Any], hour: int) -> dict[str, Any]:
    version = (await client.get(f"/api/events/{event['id']}")).json()["version"]
    r = await client.patch(
        f"/api/events/{event['id']}",
        json={
            "version": version,
            "starts_at": f"2026-11-23T{hour:02}:00:00+01:00",
            "ends_at": f"2026-11-23T{hour + 1:02}:00:00+01:00",
        },
    )
    assert r.status_code == 200, r.text
    moved: dict[str, Any] = r.json()["event"]
    return moved


async def _activity(client: AsyncClient) -> list[dict[str, Any]]:
    r = await client.get("/api/activity", params={"limit": 100})
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def test_inviting_notifies_once_and_never_posts_in_a_channel(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    t = await team(make_client, make_user, make_space)
    messages = await session.scalar(select(func.count()).select_from(Message))
    event = await new_event(t.organiser_client, t.calendar["id"], title="Planung")
    await invite(t.organiser_client, event, person(t.outsider), person(t.organiser))
    await calendar_handlers(session)
    await calendar_handlers(session, again=True)  # the worker had the events again
    told = await notes(session, t.outsider)
    assert [(n.reason, str(n.calendar_event_id)) for n in told] == [("invitation", event["id"])]
    assert await notes(session, t.organiser) == []  # never the one who invites
    assert await session.scalar(select(func.count()).select_from(Message)) == messages
    (entry,) = await _activity(t.outsider_client)
    assert (entry["reason"], entry["conversation"], entry["message_id"]) == (
        "invitation",
        None,
        None,
    )
    shown = entry["calendar_event"]
    assert (shown["id"], shown["title"], shown["response"], shown["cancelled"]) == (
        event["id"],
        "Planung",
        "needs_action",
        False,
    )
    assert (await t.outsider_client.get("/api/activity/count")).json()["unread"] == 1


async def test_a_second_change_refreshes_the_one_notification(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    t = await team(make_client, make_user, make_space)
    event = await invite(
        t.organiser_client,
        await new_event(t.organiser_client, t.calendar["id"]),
        person(t.outsider),
    )
    await calendar_handlers(session)
    (first,) = await notes(session, t.outsider)
    r = await t.outsider_client.post(f"/api/activity/{first.id}/read")
    assert r.status_code == 204
    await _move(t.organiser_client, event, 14)
    await calendar_handlers(session)
    (renewed,) = await notes(session, t.outsider)
    assert renewed.reason == "invitation"
    assert renewed.read_at is None
    assert renewed.id > first.id  # newer: on top of the list again
    await calendar_handlers(session, again=True)  # both causes again: neither is newer
    (kept,) = await notes(session, t.outsider)
    assert kept.id == renewed.id


async def test_a_time_change_resets_the_others_responses(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    t = await team(make_client, make_user, make_space)
    event = await invite(
        t.organiser_client,
        await new_event(t.organiser_client, t.calendar["id"]),
        person(t.outsider),
        person(t.reader),
        person(t.writer),
    )
    for client, said in (
        (t.outsider_client, "accepted"),
        (t.reader_client, "declined"),
        (t.writer_client, "accepted"),
    ):
        assert (await answer(client, event["id"], said)).status_code == 200
    await calendar_handlers(session)
    before = {u.id: [n.id for n in await notes(session, u)] for u in (t.outsider, t.writer)}
    version = (await t.writer_client.get(f"/api/events/{event['id']}")).json()["version"]
    titled = await t.writer_client.patch(
        f"/api/events/{event['id']}", json={"version": version, "title": "Nur Text"}
    )
    assert titled.status_code == 200
    assert set(responses(await attendees(t.writer_client, event["id"])).values()) == {
        "accepted",
        "declined",
    }  # content alone keeps every answer
    await _move(t.writer_client, event, 15)
    assert responses(await attendees(t.writer_client, event["id"])) == {
        str(t.outsider.id): "needs_action",
        str(t.reader.id): "needs_action",
        str(t.writer.id): "accepted",  # who moved it keeps hers
    }
    await calendar_handlers(session)
    renewed = await notes(session, t.outsider)
    assert [n.reason for n in renewed] == ["invitation"]
    assert [n.id for n in renewed] != before[t.outsider.id]  # told again, on top
    assert [n.id for n in await notes(session, t.writer)] == before[t.writer.id]


async def test_responding_with_a_stale_version_answers_409(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    event = await invite(
        t.organiser_client,
        await new_event(t.organiser_client, t.calendar["id"]),
        person(t.outsider),
    )
    read = (await t.outsider_client.get(f"/api/events/{event['id']}")).json()["version"]
    await _move(t.organiser_client, event, 16)
    stale = await t.outsider_client.post(
        f"/api/events/{event['id']}/response", json={"response": "accepted", "version": read}
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "event.version_conflict"
    fresh = await answer(t.outsider_client, event["id"], "accepted")
    assert fresh.status_code == 200, fresh.text
    assert (fresh.json()["principal_id"], fresh.json()["response"]) == (
        str(t.outsider.id),
        "accepted",
    )


async def test_the_organiser_hears_of_declines_only(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    t = await team(make_client, make_user, make_space)
    event = await invite(
        t.organiser_client,
        await new_event(t.organiser_client, t.calendar["id"], title="Planung"),
        person(t.outsider),
        person(t.reader),
    )
    assert (await answer(t.outsider_client, event["id"], "accepted")).status_code == 200
    await calendar_handlers(session)
    assert await notes(session, t.organiser) == []
    assert (await answer(t.reader_client, event["id"], "declined")).status_code == 200
    await calendar_handlers(session)
    assert [n.reason for n in await notes(session, t.organiser)] == ["invite_reply"]
    (entry,) = await _activity(t.organiser_client)
    assert (entry["reason"], entry["calendar_event"]["title"]) == ("invite_reply", "Planung")


async def test_cancelling_or_deleting_tells_the_attendees(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    t = await team(make_client, make_user, make_space)
    cancelled = await invite(
        t.organiser_client,
        await new_event(t.organiser_client, t.calendar["id"], title="Abgesagt"),
        person(t.outsider),
    )
    deleted = await invite(
        t.organiser_client,
        await new_event(t.organiser_client, t.calendar["id"], title="Gelöscht"),
        person(t.outsider),
    )
    r = await t.organiser_client.patch(
        f"/api/events/{cancelled['id']}",
        json={"version": cancelled["version"], "status": "cancelled"},
    )
    assert r.status_code == 200, r.text
    gone = await t.organiser_client.delete(
        f"/api/events/{deleted['id']}", params={"version": deleted["version"]}
    )
    assert gone.status_code == 204
    await calendar_handlers(session)
    shown = {e["calendar_event"]["title"]: e for e in await _activity(t.outsider_client)}
    assert {title: e["calendar_event"]["cancelled"] for title, e in shown.items()} == {
        "Abgesagt": True,
        "Gelöscht": True,
    }


async def test_the_activity_skips_reasons_this_release_does_not_know(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    t = await team(make_client, make_user, make_space)
    event = await invite(
        t.organiser_client,
        await new_event(t.organiser_client, t.calendar["id"]),
        person(t.outsider),
    )
    session.add(
        Notification(
            org_id=t.outsider.org_id,
            user_id=t.outsider.id,
            reason="event_reminder",  # a later release's reason (task 6)
            calendar_event_id=uuid.UUID(event["id"]),
        )
    )
    await session.flush()
    assert await _activity(t.outsider_client) == []
    assert (await t.outsider_client.get("/api/activity/count")).json() == {"open": 0, "unread": 0}
