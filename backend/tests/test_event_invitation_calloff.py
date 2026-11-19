"""Who hears that occurrences of a series were called off (plan M10 decision 7; review
M10 task 4, R4-1 and R4-3): the people of the row a write names, and the people of
each override the write made a tombstone or cancelled with its series; each person
once, about the first row naming her (the series before its overrides). Deleting one
occurrence tells as cancelling it does: the series' people, or the people of that
occurrence's override when it had one."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import MakeUser
from tests.factories_calendar import new_event
from tests.factories_invitations import (
    Team,
    calendar_handlers,
    invite,
    notes,
    person,
    team,
)
from tests.factories_spaces import MakeSpace

SECOND = "2026-11-30T10:00:00"  # the second Monday of the weekly series, its wall time
THIRD = "2026-12-07T10:00:00"


async def _series(t: Team, *invited: dict[str, Any]) -> dict[str, Any]:
    made = await new_event(
        t.organiser_client, t.calendar["id"], title="Jour fixe", rrule="FREQ=WEEKLY;COUNT=4"
    )
    return await invite(t.organiser_client, made, *invited) if invited else made


async def _version(client: AsyncClient, event_id: object) -> int:
    version: int = (await client.get(f"/api/events/{event_id}")).json()["version"]
    return version


async def _override(t: Team, series: dict[str, Any], *invited: dict[str, Any]) -> str:
    """An override of the second occurrence, its attendees exactly `invited`."""
    r = await t.organiser_client.patch(
        f"/api/events/{series['id']}",
        params={"scope": "this", "occurrence": SECOND},
        json={"version": await _version(t.organiser_client, series["id"]), "title": "Mit Gast"},
    )
    assert r.status_code == 200, r.text
    override: dict[str, Any] = r.json()["event"]
    await invite(t.organiser_client, override, *invited)
    return str(override["id"])


async def _told(session: AsyncSession, t: Team) -> dict[str, list[tuple[str, str]]]:
    """Each person's notifications about events after the handlers ran: (event id,
    notification id); a renewed one has a new id."""
    await calendar_handlers(session)
    found = {}
    for name, user in (("reader", t.reader), ("outsider", t.outsider), ("writer", t.writer)):
        found[name] = [(str(n.calendar_event_id), str(n.id)) for n in await notes(session, user)]
    return found


def _about(told: list[tuple[str, str]]) -> list[str]:
    return [event_id for event_id, _ in told]


async def test_a_series_moved_past_an_override_tells_its_people(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    """A new rule without the second occurrence drops its override (a tombstone)."""
    t = await team(make_client, make_user, make_space)
    series = await _series(t, person(t.reader))
    override = await _override(t, series, person(t.outsider))
    before = await _told(session, t)
    r = await t.organiser_client.patch(
        f"/api/events/{series['id']}",
        json={
            "version": await _version(t.organiser_client, series["id"]),
            "rrule": "FREQ=WEEKLY;COUNT=1",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["dropped_overrides"] == 1
    after = await _told(session, t)
    assert _about(after["outsider"]) == [override] and after["outsider"] != before["outsider"]
    assert _about(after["reader"]) == [series["id"]] and after["reader"] != before["reader"]


async def test_cutting_a_series_tells_the_people_of_the_overrides_it_drops(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    """Deleting "this and the following" from the second occurrence: the series'
    people hear about the series, the override's guest about her override."""
    t = await team(make_client, make_user, make_space)
    series = await _series(t, person(t.reader))
    override = await _override(t, series, person(t.outsider))
    before = await _told(session, t)
    gone = await t.organiser_client.delete(
        f"/api/events/{series['id']}",
        params={
            "version": await _version(t.organiser_client, series["id"]),
            "scope": "following",
            "occurrence": SECOND,
        },
    )
    assert gone.status_code == 204, gone.text
    after = await _told(session, t)
    assert _about(after["outsider"]) == [override] and after["outsider"] != before["outsider"]
    assert _about(after["reader"]) == [series["id"]] and after["reader"] != before["reader"]


async def test_deleting_an_overridden_occurrence_tells_that_override_s_people(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    """The second occurrence has its own list (the guest alone): deleting it tells
    her, not the series' people, who were not invited to it."""
    t = await team(make_client, make_user, make_space)
    series = await _series(t, person(t.reader))
    override = await _override(t, series, person(t.outsider))
    before = await _told(session, t)
    gone = await t.organiser_client.delete(
        f"/api/events/{series['id']}",
        params={
            "version": await _version(t.organiser_client, series["id"]),
            "scope": "this",
            "occurrence": SECOND,
        },
    )
    assert gone.status_code == 204, gone.text
    after = await _told(session, t)
    assert _about(after["outsider"]) == [override] and after["outsider"] != before["outsider"]
    assert after["reader"] == before["reader"]  # not renewed: nothing of hers went


async def test_someone_on_the_series_and_its_override_is_told_once(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    """Cancelling a series cancels its override too; who is on both hears about the
    series alone, who is on the override alone about the override."""
    t = await team(make_client, make_user, make_space)
    series = await _series(t, person(t.reader))
    override = await _override(t, series, person(t.reader), person(t.outsider))
    before = await _told(session, t)
    r = await t.organiser_client.patch(
        f"/api/events/{series['id']}",
        json={
            "version": await _version(t.organiser_client, series["id"]),
            "status": "cancelled",
        },
    )
    assert r.status_code == 200, r.text
    after = await _told(session, t)
    assert _about(after["reader"]) == [series["id"]] and after["reader"] != before["reader"]
    assert _about(after["outsider"]) == [override] and after["outsider"] != before["outsider"]
    assert after["writer"] == []


async def test_deleting_the_following_occurrences_tells_the_series_people(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, session: AsyncSession
) -> None:
    t = await team(make_client, make_user, make_space)
    series = await _series(t, person(t.reader))
    before = await _told(session, t)
    gone = await t.organiser_client.delete(
        f"/api/events/{series['id']}",
        params={"version": series["version"], "scope": "following", "occurrence": THIRD},
    )
    assert gone.status_code == 204, gone.text
    after = await _told(session, t)
    assert _about(after["reader"]) == [series["id"]] and after["reader"] != before["reader"]
