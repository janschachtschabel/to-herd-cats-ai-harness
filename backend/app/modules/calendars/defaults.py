"""Default calendars (plan M10 decision 2): a personal space gets one („Mein Kalender“),
the general open space („Allgemein“) one, each on the first call that lists it, once
(the space's row lock and the partial unique index on `is_default`). They are stored
without a name (the interface words them in the reader's language) until renamed, are
never archived (`service.archive`) and count within the limit of 20 calendars.

Only a person acting for herself makes them: a run (an actor with a read or write
scope) writes nothing it was not asked to, and an admin who names another person's
personal space only reads it (`member_space_ids` holds no such space)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import member_space_ids
from app.core.actor import Actor
from app.core.errors import NotFound
from app.core.principal import PrincipalType
from app.modules.calendars.models import MAX_CALENDARS_PER_SPACE, Calendar, CalendarColor
from app.modules.calendars.repository import CalendarRepository
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.service import GENERAL_SPACE_NAME

DEFAULT_COLOR = CalendarColor.BLUE


def wants_default(space: Space) -> bool:
    """Whether the space has a default calendar (made when first listed)."""
    return space.kind == SpaceKind.PERSONAL or (
        space.kind == SpaceKind.OPEN and space.name == GENERAL_SPACE_NAME
    )


async def ensure_default(
    session: AsyncSession, actor: Actor, space_id: uuid.UUID
) -> Calendar | None:
    """The space's default calendar, made now if it has none (under the space's row
    lock, so calendars of one space are made one after the other). The default counts
    within `MAX_CALENDARS_PER_SPACE`: None when the space is full without one (an open
    space that held 20 calendars when it became the general space). A personal space
    is never full without it: `service.create` makes the default first."""
    repo = CalendarRepository(session, actor.org_id)
    if (found := await repo.default_of(space_id)) is not None:
        return found
    space = await repo.lock_space(space_id)
    if space is None:
        raise NotFound(code="space.not_found")
    if (found := await repo.default_of(space_id)) is not None:  # made while we waited
        return found
    if await repo.count_active(space_id) >= MAX_CALENDARS_PER_SPACE:
        return None
    await repo.insert_default(space_id, DEFAULT_COLOR)
    made = await repo.default_of(space_id)
    assert made is not None  # inserted now, or by a transaction that committed first
    return made


async def ensure_defaults(
    session: AsyncSession, actor: Actor, *, only: uuid.UUID | None = None
) -> None:
    """The defaults still missing in the actor's own personal space and the general
    space (with `only`: in that space alone), for a person acting for herself."""
    if actor.principal.type != PrincipalType.USER:
        return
    if actor.read_scope is not None or actor.write_scope is not None:
        return
    repo = CalendarRepository(session, actor.org_id)
    due = await repo.defaults_due(
        member_space_ids(actor), actor.principal.id, GENERAL_SPACE_NAME, only=only
    )
    for space_id in due:
        await ensure_default(session, actor, space_id)
