"""Invitations to a series (plan M10 task 4, decision 6, I5 and I6): an override starts
with a copy of its series' attendees and answers (`series.ON_OVERRIDE`), the part a
split makes takes them along (`series_split.CARRY`); from then on answers hold per
row. Who is invited to one override sees that occurrence only; who is removed from
one sees the series without it. Changing a series' attendees reaches its overrides
(the people added and removed); answering a series reaches the overrides whose answer
followed the series'."""

from typing import Any

from httpx import AsyncClient

from tests.factories import MakeUser
from tests.factories_calendar import logged_in, new_event, window
from tests.factories_invitations import (
    SPAN,
    Team,
    answer,
    attendees,
    invite,
    person,
    responses,
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


async def _change(
    client: AsyncClient, event: dict[str, Any], scope: str, occurrence: str, **body: Any
) -> dict[str, Any]:
    version = (await client.get(f"/api/events/{event['id']}")).json()["version"]
    r = await client.patch(
        f"/api/events/{event['id']}",
        params={"scope": scope, "occurrence": occurrence},
        json={"version": version, **body},
    )
    assert r.status_code == 200, r.text
    changed: dict[str, Any] = r.json()["event"]
    return changed


async def test_an_override_inherits_attendees(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    series = await _series(t, person(t.outsider), person(t.reader, "optional"))
    assert (await answer(t.outsider_client, series["id"], "accepted")).status_code == 200
    override = await _change(t.organiser_client, series, "this", SECOND, title="Anders")
    copied = await attendees(t.organiser_client, override["id"])
    assert responses(copied) == {str(t.outsider.id): "accepted", str(t.reader.id): "needs_action"}
    assert {a["principal_id"]: a["role"] for a in copied}[str(t.reader.id)] == "optional"
    # From now on, answers hold per row.
    assert (await answer(t.outsider_client, override["id"], "declined")).status_code == 200
    assert responses(await attendees(t.organiser_client, series["id"]))[str(t.outsider.id)] == (
        "accepted"
    )


async def test_someone_invited_to_one_occurrence_sees_only_that_one(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    removed = await make_user()
    series = await _series(t, person(removed))
    override = await _change(t.organiser_client, series, "this", SECOND, title="Mit Gast")
    await invite(t.organiser_client, override, person(t.outsider))
    found = await window(t.outsider_client, *SPAN)
    assert [(o["event_id"], o["title"]) for o in found] == [(override["id"], "Mit Gast")]
    assert (await t.outsider_client.get(f"/api/events/{series['id']}")).status_code == 404
    # Removed from that override (by the same write): the series without it.
    removed_client = await logged_in(make_client, removed)
    starts = [o["start"] for o in await window(removed_client, *SPAN)]
    assert len(starts) == 3
    assert "2026-11-30T09:00:00Z" not in starts


async def test_a_split_carries_attendees_and_answers(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    series = await _series(t, person(t.outsider), person(t.reader))
    assert (await answer(t.outsider_client, series["id"], "accepted")).status_code == 200
    assert (await answer(t.reader_client, series["id"], "tentative")).status_code == 200
    new = await _change(t.organiser_client, series, "following", THIRD, title="Neu")
    assert new["id"] != series["id"]
    assert responses(await attendees(t.organiser_client, new["id"])) == {
        str(t.outsider.id): "accepted",  # the time stays: so do the answers
        str(t.reader.id): "tentative",
    }
    titles = [o["title"] for o in await window(t.outsider_client, *SPAN)]
    assert titles == ["Jour fixe", "Jour fixe", "Neu", "Neu"]


async def test_a_series_attendee_change_reaches_its_overrides(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    series = await _series(t, person(t.reader))
    override = await _change(t.organiser_client, series, "this", SECOND, title="Anders")
    await invite(t.organiser_client, series, person(t.outsider))  # reader out, outsider in
    assert responses(await attendees(t.organiser_client, override["id"])) == {
        str(t.outsider.id): "needs_action"
    }
    assert len(await window(t.outsider_client, *SPAN)) == 4


async def test_answering_a_series_reaches_the_overrides_that_followed_it(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    t = await team(make_client, make_user, make_space)
    series = await _series(t, person(t.outsider))
    followed = await _change(t.organiser_client, series, "this", SECOND, title="A")
    own = await _change(t.organiser_client, series, "this", THIRD, title="B")
    assert (await answer(t.outsider_client, own["id"], "declined")).status_code == 200
    assert (await answer(t.outsider_client, series["id"], "accepted")).status_code == 200
    for event_id, expected in (
        (series["id"], "accepted"),
        (followed["id"], "accepted"),
        (own["id"], "declined"),  # answered on its own: stays
    ):
        got = responses(await attendees(t.organiser_client, event_id))
        assert got == {str(t.outsider.id): expected}
