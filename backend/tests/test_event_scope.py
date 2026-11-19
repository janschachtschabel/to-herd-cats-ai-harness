"""A run's read scope holds for events too (review M10 task 3a, R3a-10): the organiser
shortcut of `sight` gives an actor with a `read_scope` nothing outside it, by id or in
the window, as `core/access.py` applies a scope to any actor. And the event services
leave SQL to `sight.py` and the repository (R3a-6)."""

import ast
import dataclasses
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import ReadScope
from app.core.errors import NotFound
from app.core.pagination import PageParams
from app.core.permissions import SpaceRole
from app.modules.calendars.events import EventService
from app.modules.calendars.window import list_window
from tests.factories import MakeUser
from tests.factories_calendar import actor_of, logged_in, new_calendar, new_event
from tests.factories_spaces import MakeSpace

CALENDARS = Path(__file__).parent.parent / "app" / "modules" / "calendars"


async def test_the_organiser_shortcut_stays_inside_a_read_scope(
    session: AsyncSession, make_client: Any, make_user: MakeUser, make_space: MakeSpace
) -> None:
    author = await make_user()
    team = await make_space("team", members=[(author, "moderator")])
    other = await make_space("team", members=[(author, "moderator")])
    client = await logged_in(make_client, author)
    made = await new_event(client, (await new_calendar(client, team.id))["id"], title="Kur")
    event_id = uuid.UUID(made["id"])
    actor = await actor_of(session, author)
    seen = await EventService(session).get(actor, event_id)
    assert seen.event.id == event_id
    elsewhere = dataclasses.replace(actor, read_scope=ReadScope.of({other.id: SpaceRole.ADMIN}))

    async def window_ids(who: Any, *, mine: bool) -> list[uuid.UUID]:
        page = await list_window(
            session,
            who,
            start=datetime(2026, 11, 23, tzinfo=UTC),
            end=datetime(2026, 11, 24, tzinfo=UTC),
            calendar_ids=None,
            space_id=None,
            mine=mine,
            query=None,
            params=PageParams(),
        )
        return [o.event_id for o in page.items]

    assert await window_ids(actor, mine=True) == [event_id]
    with pytest.raises(NotFound) as caught:
        await EventService(session).get(elsewhere, event_id)
    assert caught.value.code == "event.not_found"
    assert await window_ids(elsewhere, mine=False) == []
    assert await window_ids(elsewhere, mine=True) == []
    inside = dataclasses.replace(actor, read_scope=ReadScope.of({team.id: SpaceRole.VIEWER}))
    assert (await EventService(session).get(inside, event_id)).event.id == event_id


def test_the_event_services_build_no_sql() -> None:
    """R3a-6 (hard rule 3): the services of events take their SQL from `sight.py` and
    the repository; they import nothing from SQLAlchemy but the session."""
    for name in (
        "events.py",
        "window.py",
        "event_writes.py",
        "series.py",
        "series_rebase.py",
        "series_split.py",
    ):
        tree = ast.parse((CALENDARS / name).read_text())
        imported = {
            (node.module, alias.name)
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("sqlalchemy")
            for alias in node.names
        }
        assert imported == {("sqlalchemy.ext.asyncio", "AsyncSession")}, name
