"""What a run may read and where it may write, by the audience of the place it answers
in (spec 5.6, plan M6 decision 5). The run acts as the person who asked (their own
rights apply as they are), held to

- **read**: the agent's roles (its memberships, `viewer` in the open spaces), only in
  the spaces the place's audience may see:

  | place                                    | read (∩ agent)           | write        |
  |------------------------------------------|--------------------------|--------------|
  | DM of the person alone with the agent    | all                      | no limit     |
  | DM with several people                   | spaces all of them read  | those spaces |
  | channel, page or ticket thread in S      | S and the open spaces    | S            |

  In a place in S, the open spaces count only while S has no guest among its members
  (directly or through a group): guests read no open space, so its content would reach
  them (stricter than spec 5.6, which names S and the open spaces). S open: the same
  rule (S is one of the open spaces).
- **write**: in a DM alone, wherever the person and the agent both may (their rights
  decide); otherwise only in the spaces above.

The result is a `ReadScope` and a `WriteScope` on the run's actor; the one permission
check applies both to whoever carries them (`core/access.py`), nothing here or there
knows it is an agent. Computed anew for every check of the run, so a person who joins
or leaves a DM, or a space that changes, counts at once.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import ReadScope, WriteScope
from app.core.permissions import SpaceRole
from app.modules.agents.scope_repository import ScopeRepository
from app.modules.messaging.models import ConversationKind


class PlaceKind(StrEnum):
    ALONE = "alone"  # a DM of the person with the agent only
    DM = "dm"  # a DM with several people
    SPACE = "space"  # a channel, page thread or ticket thread in a space


@dataclass(frozen=True, slots=True)
class Place:
    kind: PlaceKind
    space_id: uuid.UUID | None = None  # SPACE
    people: frozenset[uuid.UUID] = frozenset()  # DM: its active people


@dataclass(frozen=True, slots=True)
class Scopes:
    read: ReadScope
    write: WriteScope | None


async def place_of(
    session: AsyncSession, org_id: uuid.UUID, conversation_id: uuid.UUID, asker: uuid.UUID
) -> Place | None:
    """The place of the conversation a run answers in (None: it is gone)."""
    repo = ScopeRepository(session, org_id)
    found = await repo.conversation(conversation_id)
    if found is None:
        return None
    kind, space_id = found
    if kind != ConversationKind.DM:
        return Place(PlaceKind.SPACE, space_id=space_id)
    people = await repo.people(conversation_id)
    if people <= {asker}:
        return Place(PlaceKind.ALONE)
    return Place(PlaceKind.DM, people=people | {asker})


async def scopes(
    session: AsyncSession,
    org_id: uuid.UUID,
    place: Place,
    agent_roles: dict[uuid.UUID, SpaceRole],
) -> Scopes:
    if place.kind == PlaceKind.ALONE:
        return Scopes(ReadScope.of(agent_roles), None)
    repo = ScopeRepository(session, org_id)
    if place.kind == PlaceKind.DM:
        seen = await repo.read_by_all(set(agent_roles), place.people)
        return Scopes(_only(agent_roles, seen), WriteScope.of(seen))
    assert place.space_id is not None
    audience = await space_audience(session, org_id, place.space_id)
    return Scopes(_only(agent_roles, audience), WriteScope.of({place.space_id}))


async def space_audience(
    session: AsyncSession, org_id: uuid.UUID, space_id: uuid.UUID
) -> set[uuid.UUID]:
    """The spaces whose content the audience of a place in the space may receive: the
    space, and the open spaces while it has no guest. A writing tool writes into a
    space only what came from these (plan M6 review focus 1)."""
    repo = ScopeRepository(session, org_id)
    audience = {space_id}
    if not await repo.has_guests(space_id):
        audience |= await repo.open_ids()
    return audience


async def organisation_audience(session: AsyncSession, org_id: uuid.UUID) -> set[uuid.UUID]:
    """The spaces whose content may go where everyone of the organisation with AI
    reads it (an organisation-wide skill; guests have no AI): the open spaces."""
    return await ScopeRepository(session, org_id).open_ids()


def _only(roles: dict[uuid.UUID, SpaceRole], spaces: set[uuid.UUID]) -> ReadScope:
    return ReadScope.of({sid: role for sid, role in roles.items() if sid in spaces})
