"""The stock of the calendar's expansion measurement (plan M10 Task 3c), written straight
into a database of its own (never a shared one): every event through
`event_times.check`, as the API stores it, so `recurs_until` and the canonical rule
are what production writes.

- The window (cases `week`, `month`): a viewer (member of four team spaces) and 20 team
  calendars (five per space) holding 500 series (mixed rules, a third endless, starts
  up to five years back, some EXDATEs and moved occurrences) and 5,000 single events
  (a year to either side of the anchor, some all-day, some private, tentative or
  cancelled).
- Availability (`availability_*`): 20 people, each with a personal calendar of 25
  series and 250 single events from the same mixture (500 and 5,000 in all).
- `idle`: 4,001 yearly all-day birthdays in March, endless, in one calendar its own
  viewer reads (review M10 task 3a, R3a-2).
- `bound`: `BOUND_SERIES` endless yearly March series in one calendar, near the
  expansion's work bound (`expansion.MAX_WORK`, ≈ 12,500 rows).
"""

import random
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.calendars.event_models import CalendarEvent
from app.modules.calendars.models import Calendar, CalendarColor
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository
from app.modules.spaces.service import SpaceService
from app.modules.users.models import User
from scripts.measure_calendar_events import (
    ANCHOR,
    ZONE,
    birthday_row,
    drawn,
    march_row,
    series_rows,
    single_row,
)

__all__ = ["ANCHOR", "ZONE", "Stock", "find", "seed"]

ORG_NAME = "Messung Kalender (M10 Task 3c)"
PEOPLE = 20
TEAM_SPACES, CALENDARS_PER_SPACE = 4, 5
SERIES, SINGLES = 500, 5000
IDLE_SERIES = 4001
BOUND_SERIES = 12_000


@dataclass
class Stock:
    org_id: uuid.UUID
    viewer: User
    idle_viewer: User
    bound_viewer: User
    people: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)  # space → person


def _email(name: str) -> str:
    return f"{name}@messung.example"


async def find(session: AsyncSession) -> Stock | None:
    org = await session.scalar(select(Organization).where(Organization.name == ORG_NAME))
    if org is None:
        return None
    users = {u.email: u for u in await session.scalars(select(User).where(User.org_id == org.id))}
    people = {}
    for i in range(PEOPLE):
        person = users[_email(f"person{i:02d}")]
        space = await SpaceRepository(session).get_personal(org.id, person.id)
        assert space is not None
        people[space.id] = person.id
    return Stock(
        org.id,
        users[_email("viewer")],
        users[_email("idle")],
        users[_email("bound")],
        people,
    )


async def seed(session: AsyncSession, password_hash: str) -> Stock:
    rng = random.Random(3)  # noqa: S311 - the same stock every time, no secret
    org = Organization(name=ORG_NAME)
    session.add(org)
    await session.flush()

    async def user(name: str) -> User:
        made = User(
            org_id=org.id,
            email=_email(name),
            name=name,
            password_hash=password_hash,
            system_role=SystemRole.MEMBER,
            is_active=True,
        )
        session.add(made)
        await session.flush()
        await SpaceService(session).create_personal(made)
        return made

    viewer, idle, bound = await user("viewer"), await user("idle"), await user("bound")
    persons = [await user(f"person{i:02d}") for i in range(PEOPLE)]
    stock = Stock(org.id, viewer, idle, bound)
    calendars = []
    for s in range(TEAM_SPACES):
        space = await _team_space(session, org.id, f"Team {s + 1}", viewer)
        calendars += [
            await _calendar(session, org.id, space.id, f"Kalender {s + 1}.{c + 1}")
            for c in range(CALENDARS_PER_SPACE)
        ]
    organisers = [p.id for p in persons]
    await _events(session, rng, org.id, calendars, organisers, SERIES, SINGLES)
    for person in persons:
        personal = await SpaceRepository(session).get_personal(org.id, person.id)
        assert personal is not None
        stock.people[personal.id] = person.id
        mine = [await _calendar(session, org.id, personal.id, None)]
        await _events(session, rng, org.id, mine, [person.id], SERIES // PEOPLE, SINGLES // PEOPLE)
    idle_space = await _team_space(session, org.id, "Geburtstage", idle)
    birthdays = await _calendar(session, org.id, idle_space.id, "Geburtstage")
    await _insert(
        session, [birthday_row(rng, org.id, birthdays, idle.id) for _ in range(IDLE_SERIES)]
    )
    bound_space = await _team_space(session, org.id, "Grenze", bound)
    near = await _calendar(session, org.id, bound_space.id, "Grenze")
    await _insert(session, [march_row(rng, org.id, near, bound.id) for _ in range(BOUND_SERIES)])
    return stock


async def _team_space(session: AsyncSession, org_id: uuid.UUID, name: str, member: User) -> Space:
    spaces = SpaceRepository(session)
    space = await spaces.add(Space(org_id=org_id, kind=SpaceKind.TEAM, name=name))
    await spaces.set_member(space.id, Principal.user(member.id), SpaceRole.EDITOR)
    return space


async def _calendar(
    session: AsyncSession, org_id: uuid.UUID, space_id: uuid.UUID, name: str | None
) -> Calendar:
    made = Calendar(
        org_id=org_id,
        space_id=space_id,
        name=name,
        color=CalendarColor.BLUE,
        is_default=name is None,
        time_zone=ZONE,
    )
    session.add(made)
    await session.flush()
    return made


async def _events(
    session: AsyncSession,
    rng: random.Random,
    org_id: uuid.UUID,
    calendars: list[Calendar],
    organisers: list[uuid.UUID],
    series: int,
    singles: int,
) -> None:
    rows: list[dict[str, Any]] = []
    for _ in range(series):
        rows += drawn(
            lambda: series_rows(rng, org_id, rng.choice(calendars), rng.choice(organisers))
        )
    rows += [
        single_row(rng, org_id, rng.choice(calendars), rng.choice(organisers))
        for _ in range(singles)
    ]
    await _insert(session, rows)


async def _insert(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    masters = [r for r in rows if "series_id" not in r]
    overrides = [r for r in rows if "series_id" in r]
    for part in (masters, overrides):  # an override refers to its master
        for i in range(0, len(part), 1000):
            await session.execute(
                insert(CalendarEvent),
                [{"series_id": None, "recurrence_id": None, **r} for r in part[i : i + 1000]],
            )
