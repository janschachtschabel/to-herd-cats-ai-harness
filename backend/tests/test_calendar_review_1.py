"""Review of M10 Task 1 (`.superpowers/sdd/m10/review-task-1.md`): each test proves one
finding and fails until it is fixed."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.calendars.defaults import ensure_default
from app.modules.calendars.service import CalendarService
from tests.factories import MakeUser, login
from tests.factories_calendar import actor_of, listed
from tests.factories_spaces import personal_space_of


async def _client(make_client: Any, email: str) -> AsyncClient:
    client: AsyncClient = await make_client(csrf=True)
    await login(client, email)
    return client


async def test_ensure_default_never_hands_out_an_archived_calendar(
    session: AsyncSession, make_user: MakeUser
) -> None:
    """R1-I1: `ensure_default` is what later tasks use to find a person's own calendar.
    Once the default is archived (nothing refuses that), it must not return the
    archived row: either archiving a default is refused, or a new default is made."""
    person = await make_user()
    actor = await actor_of(session, person)
    own = await personal_space_of(session, person)
    service = CalendarService(session)
    default = await ensure_default(session, actor, own.id)
    try:
        await service.archive(actor, default.id, default.version)
    except AppError:
        pass  # refusing to archive a default is one valid fix
    found = await ensure_default(session, actor, own.id)
    assert found is not None and found.archived_at is None
    assert (await service.readable(actor, found.id)).id == found.id


async def test_a_person_who_archived_mein_kalender_still_has_a_personal_calendar(
    session: AsyncSession, make_client: Any, make_user: MakeUser
) -> None:
    """R1-I1 through the API: the personal default is the calendar decision 2 promises
    every person; archiving has no way back (no unarchive, never recreated)."""
    person = await make_user()
    client = await _client(make_client, person.email)
    (default,) = await listed(client)
    await client.delete(f"/api/calendars/{default['id']}", params={"version": default["version"]})
    assert [c["is_default"] for c in await listed(client)] == [True]
