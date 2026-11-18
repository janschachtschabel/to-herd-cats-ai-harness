"""Default calendars (plan M10 decision 2, review of task 1): a default is kept (never
archived), counts within the limit of 20, and is stored without a name until someone
renames it (the interface names it in the reader's language)."""

import asyncio
import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import member_space_ids
from app.modules.calendars.models import MAX_CALENDARS_PER_SPACE, Calendar
from app.modules.calendars.repository import CalendarRepository
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.service import GENERAL_SPACE_NAME
from app.modules.users.models import User
from tests.factories import MakeUser, login
from tests.factories_calendar import actor_of, listed, new_calendar
from tests.factories_spaces import MakeSpace, personal_space_of
from tests.real_db import MakeRealClient, RealDb


async def _client(make_client: Any, user: User) -> AsyncClient:
    client: AsyncClient = await make_client(csrf=True)
    await login(client, user.email)
    return client


async def test_a_default_calendar_cannot_be_archived(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """R1-I1: archiving „Mein Kalender“ or the general space's calendar answers 409
    `calendar.default_kept`; the calendar stays, at its version."""
    person = await make_user()
    await make_space("open", GENERAL_SPACE_NAME, members=[(person, "moderator")])
    client = await _client(make_client, person)
    defaults = await listed(client)
    assert len(defaults) == 2 and all(c["is_default"] for c in defaults)
    for calendar in defaults:
        url = f"/api/calendars/{calendar['id']}"
        r = await client.delete(url, params={"version": calendar["version"]})
        assert (r.status_code, r.json()["error"]["code"]) == (409, "calendar.default_kept")
    assert await listed(client) == defaults
    team = await make_space("team", members=[(person, "moderator")])
    other = await new_calendar(client, team.id)
    r = await client.delete(f"/api/calendars/{other['id']}", params={"version": 1})
    assert r.status_code == 204  # other calendars are archived as before


async def test_a_default_calendar_has_no_stored_name_until_renamed(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """R1-M5: „Mein Kalender“ and „Allgemein“ are words of the interface (rule 11): the
    API says `name: null` and `is_default`; a name someone gives is kept as given."""
    person = await make_user()
    general = await make_space("open", GENERAL_SPACE_NAME, members=[(person, "moderator")])
    client = await _client(make_client, person)
    own = await personal_space_of(session, person)
    found = await listed(client)
    assert sorted((c["space_id"], c["name"], c["is_default"]) for c in found) == sorted(
        [(str(own.id), None, True), (str(general.id), None, True)]
    )
    mine = next(c for c in found if c["space_id"] == str(own.id))
    url = f"/api/calendars/{mine['id']}"
    r = await client.patch(url, json={"name": "Privat", "version": mine["version"]})
    assert (r.status_code, r.json()["name"], r.json()["is_default"]) == (200, "Privat", True)
    r = await client.patch(url, json={"name": None, "version": r.json()["version"]})
    assert r.status_code == 422  # a name once given is not taken back to null


async def test_the_default_counts_within_the_limit(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    """R1-M1: an open space that already holds 20 calendars when it becomes the general
    space (renamed, or a second one of that name) gets no 21st as its default."""
    person = await make_user()
    space = await make_space("open", "Bald allgemein", members=[(person, "moderator")])
    client = await _client(make_client, person)
    for i in range(MAX_CALENDARS_PER_SPACE):
        await new_calendar(client, space.id, f"K{i}")
    space.name = GENERAL_SPACE_NAME
    await session.flush()
    url = f"/api/spaces/{space.id}/calendars"
    for _ in range(2):  # the named way and the list
        assert len(await listed(client, url)) == MAX_CALENDARS_PER_SPACE
        assert [c for c in await listed(client) if c["space_id"] == str(space.id)] == [
            c for c in await listed(client, url)
        ]
    assert not any(c["is_default"] for c in await listed(client, url))


async def test_spaces_due_a_default_come_in_the_order_they_are_locked(
    session: AsyncSession, make_user: MakeUser
) -> None:
    """R1-M3: `ensure_defaults` locks the spaces in the order `defaults_due` gives them;
    by id, so two first calls of one person never lock in opposite orders."""
    person = await make_user()
    own = await personal_space_of(session, person)
    general = Space(  # stored after her personal space, with the smaller id
        id=uuid.UUID(int=1), org_id=person.org_id, kind=SpaceKind.OPEN, name=GENERAL_SPACE_NAME
    )
    session.add(general)
    await session.flush()
    actor = await actor_of(session, person)
    due = await CalendarRepository(session, person.org_id).defaults_due(
        member_space_ids(actor), person.id, GENERAL_SPACE_NAME
    )
    assert due == [general.id, own.id]


async def test_the_general_default_is_made_once_for_two_first_callers(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    """R1-M7: two people's first calls at once make the general space's default once
    (the space's row lock and the partial unique index)."""
    async with real_db.database.session_factory() as session, session.begin():
        general = Space(org_id=real_db.org_id, kind=SpaceKind.OPEN, name=GENERAL_SPACE_NAME)
        session.add(general)
    clients = []
    for email in (real_db.owner_email, real_db.member_email) * 3:
        client = await make_real_client()
        await login(client, email)
        clients.append(client)
    answers = await asyncio.gather(*(c.get("/api/calendars") for c in clients))
    assert [a.status_code for a in answers] == [200] * 6, [a.text for a in answers]
    async with real_db.database.session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(Calendar).where(Calendar.space_id == general.id)
        )
    assert count == 1
    general_ids = {
        c["id"] for a in answers for c in a.json()["items"] if c["space_id"] == str(general.id)
    }
    assert len(general_ids) == 1
