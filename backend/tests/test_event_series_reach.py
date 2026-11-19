"""A series operation and its overrides (review M10 task 3b, R3b-1, R3b-2, R3b-8, R3b-12).

- Every override a series operation writes (deletes, drops, moves, re-homes, changes)
  needs the writer's full sight, like the series (decision 3, C2): with "busy" sight of
  one, the whole operation is 403 `event.private`, in a dry run too, and nothing is
  written. Admin power that shows such an override is audited.
- `scope=all` content reaches each override field that still holds the series' old
  value; private and cancelled reach every override; "this and the following" reaches
  the overrides it carries the same way.
- An EXDATE sent for an overridden occurrence drops the override.
- The series' outbox event names the overrides the operation wrote (ids only).
"""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.core.principal import SystemRole
from app.modules.audit.models import CALENDAR_ADMIN_WRITE
from tests.factories import MakeUser
from tests.factories_calendar import logged_in, new_calendar, new_event, window
from tests.factories_spaces import MakeSpace
from tests.test_event_writes import _audit, _code, _team, delete, patch

MONDAYS = {
    "starts_at": "2026-11-23T09:00:00+01:00",
    "ends_at": "2026-11-23T10:00:00+01:00",
}
SPAN = ("2026-11-16T00:00:00Z", "2027-01-31T00:00:00Z")
SECOND = "2026-11-30T09:00:00"


async def _with_private_override(
    client: AsyncClient, calendar_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mondays from 23 November (four), the second one made private by the organiser."""
    made = await new_event(client, calendar_id, rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS)
    hidden = await patch(
        client,
        made,
        title="Geheim",
        visibility="private",
        query={"scope": "this", "occurrence": SECOND},
    )
    assert hidden.status_code == 200, hidden.text
    return made, hidden.json()["event"]


OPERATIONS: dict[str, tuple[str, dict[str, Any]]] = {
    "delete all": ("delete", {}),
    "delete this": ("delete", {"scope": "this", "occurrence": SECOND}),
    "delete following": ("delete", {"scope": "following", "occurrence": SECOND}),
    "rule drops it": ("patch", {"rrule": "FREQ=WEEKLY;COUNT=1"}),
    "rule drops it, dry run": ("patch", {"rrule": "FREQ=WEEKLY;COUNT=1", "dry": True}),
    "move": (
        "patch",
        {"starts_at": "2026-11-23T10:00:00+01:00", "ends_at": "2026-11-23T11:00:00+01:00"},
    ),
    "exdate": ("patch", {"exdates": [SECOND]}),
    "split re-homes it": ("patch", {"title": "Neu", "following": "2026-11-30T09:00:00"}),
    "cancel": ("patch", {"status": "cancelled"}),
    "cancel, dry run": ("patch", {"status": "cancelled", "dry": True}),
}


@pytest.mark.parametrize("name", list(OPERATIONS))
async def test_no_series_operation_reaches_an_override_the_writer_sees_as_busy(
    name: str, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    made, override = await _with_private_override(team.organiser_client, team.calendar["id"])
    verb, args = OPERATIONS[name]
    if verb == "delete":
        r = await delete(team.writer_client, made, **args)
    else:
        body = dict(args)
        query: dict[str, Any] = {"dry_run": "true"} if body.pop("dry", False) else {}
        if "following" in body:
            query |= {"scope": "following", "occurrence": body.pop("following")}
        r = await patch(team.writer_client, made, query=query, **body)

    assert _code(r) == (403, "event.private")
    still = await team.organiser_client.get(f"/api/events/{override['id']}")
    assert (still.status_code, still.json()["version"]) == (200, override["version"])
    series = (await team.organiser_client.get(f"/api/events/{made['id']}")).json()
    assert series["version"] == made["version"]


async def test_the_organiser_reaches_her_private_override(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    made, override = await _with_private_override(team.organiser_client, team.calendar["id"])
    assert (await delete(team.organiser_client, made)).status_code == 204
    assert (await team.organiser_client.get(f"/api/events/{override['id']}")).status_code == 404


async def test_an_admin_reaching_a_private_override_by_admin_power_is_audited(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """The series is not private, its override is: a member admin who deletes the
    series sees the override only by admin power, and the write is audited."""
    organiser, member_admin = await make_user(), await make_user(SystemRole.ADMIN)
    space = await make_space("team", members=[(organiser, "moderator"), (member_admin, "editor")])
    organiser_client = await logged_in(make_client, organiser)
    calendar = await new_calendar(organiser_client, space.id, "Team")
    made, _ = await _with_private_override(organiser_client, calendar["id"])
    admin = await logged_in(make_client, member_admin)

    assert (await delete(admin, made)).status_code == 204

    writes = [e for e in await _audit(session, member_admin) if e.action == CALENDAR_ADMIN_WRITE]
    assert [(str(e.target_id), e.details["change"]) for e in writes] == [(made["id"], "delete")]


async def _outbox(session: AsyncSession, event_id: str) -> list[tuple[str, dict[str, Any]]]:
    rows = await session.scalars(
        select(EventOutbox)
        .where(EventOutbox.subject_id == uuid.UUID(event_id))
        .order_by(EventOutbox.id)
    )
    return [(row.type, row.payload) for row in rows]


async def test_renaming_a_series_reaches_what_its_overrides_kept(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    client = team.organiser_client
    made = await new_event(
        client, team.calendar["id"], location="Raum 1", rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS
    )
    moved = await patch(
        client,
        made,
        starts_at="2026-11-30T14:00:00+01:00",
        ends_at="2026-11-30T15:00:00+01:00",
        query={"scope": "this", "occurrence": SECOND},
    )
    own = await patch(
        client, made, title="Eigen", query={"scope": "this", "occurrence": "2026-12-07T09:00:00"}
    )
    a, b = moved.json()["event"], own.json()["event"]

    renamed = await patch(client, made, title="Neu", location="Raum 2")

    assert renamed.status_code == 200, renamed.text
    read_a = (await client.get(f"/api/events/{a['id']}")).json()
    read_b = (await client.get(f"/api/events/{b['id']}")).json()
    assert (read_a["title"], read_a["location"], read_a["starts_at"]) == (
        "Neu",
        "Raum 2",
        "2026-11-30T13:00:00Z",
    )
    assert (read_b["title"], read_b["location"]) == ("Eigen", "Raum 2")
    assert (read_a["version"], read_b["version"]) == (a["version"] + 1, b["version"] + 1)
    _, payload = (await _outbox(session, made["id"]))[-1]
    assert payload == {
        "calendar_id": team.calendar["id"],
        "fields": ["location", "title"],
        "overrides": sorted([a["id"], b["id"]]),
    }


async def test_cancelling_a_series_reaches_every_override(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """A tentative override is cancelled with its series (whatever it held); confirming
    the series again reaches it like any field that holds the series' old value."""
    team = await _team(make_client, make_user, make_space)
    client = team.organiser_client
    made = await new_event(client, team.calendar["id"], rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS)
    own = await patch(
        client, made, status="tentative", query={"scope": "this", "occurrence": SECOND}
    )
    override = own.json()["event"]

    assert (await patch(client, made, status="cancelled")).status_code == 200

    assert (await client.get(f"/api/events/{override['id']}")).json()["status"] == "cancelled"
    series = (await client.get(f"/api/events/{made['id']}")).json()
    assert (await patch(client, series, status="confirmed")).status_code == 200
    assert (await client.get(f"/api/events/{override['id']}")).json()["status"] == "confirmed"


async def test_this_and_the_following_reaches_the_overrides_it_carries(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    client = team.organiser_client
    made = await new_event(client, team.calendar["id"], rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS)
    later = await patch(
        client,
        made,
        location="Raum 9",
        query={"scope": "this", "occurrence": "2026-12-14T09:00:00"},
    )
    override = later.json()["event"]

    split = await patch(
        client,
        made,
        title="Neu",
        visibility="private",
        query={"scope": "following", "occurrence": "2026-12-07T09:00:00"},
    )

    assert split.status_code == 200, split.text
    read = (await client.get(f"/api/events/{override['id']}")).json()
    assert (read["title"], read["location"], read["visibility"]) == ("Neu", "Raum 9", "private")
    assert read["series_id"] == split.json()["event"]["id"]


async def test_an_exdate_sent_for_an_overridden_occurrence_drops_the_override(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    team = await _team(make_client, make_user, make_space)
    client = team.organiser_client
    made = await new_event(client, team.calendar["id"], rrule="FREQ=WEEKLY;COUNT=4", **MONDAYS)
    own = await patch(client, made, title="Eigen", query={"scope": "this", "occurrence": SECOND})
    override = own.json()["event"]
    query = {"dry_run": "true"}
    dry = await patch(client, made, exdates=[SECOND], query=query)
    assert (dry.json()["dropped_overrides"], dry.json()["dropped_exdates"]) == (1, 0)

    sent = await patch(client, made, exdates=[SECOND])

    assert (sent.json()["dropped_overrides"], sent.json()["dropped_exdates"]) == (1, 0)
    assert (await client.get(f"/api/events/{override['id']}")).status_code == 404
    titles = [o["title"] for o in await window(client, *SPAN)]
    assert titles == ["Termin", "Termin", "Termin"]
