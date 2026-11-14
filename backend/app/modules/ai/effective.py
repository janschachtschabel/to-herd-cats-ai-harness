"""`ai.use`, derived (plan M5 decision 5; spec 7.2): never stored on the person.

The first assignment that applies decides (person, then the first matching group,
then the organisation's standard). It grants `ai.use` only if the person is active
and no guest, it is not "no AI", and its connection is enabled, made for chat and
still lists the model. A disabled connection does not hand the person on to the next
assignment: that one could send their content somewhere the admin did not choose.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.ai.assignment_repository import AssignmentRepository, Resolved
from app.modules.ai.models import Purpose

CHAT_PURPOSES = frozenset({Purpose.CHAT, Purpose.BOTH})


@dataclass(frozen=True, slots=True)
class Effective:
    source: str
    connection_id: uuid.UUID
    model: str


def judge(resolved: Resolved | None) -> Effective | None:
    if resolved is None or not resolved.is_active or resolved.system_role == SystemRole.GUEST:
        return None
    if resolved.source is None or resolved.no_ai:
        return None
    if resolved.connection_id is None or resolved.model is None:
        return None
    usable = (
        resolved.connection_enabled is True
        and resolved.connection_purpose in CHAT_PURPOSES
        and resolved.model_listed is True
    )
    return Effective(resolved.source, resolved.connection_id, resolved.model) if usable else None


async def effective_assignment(
    session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
) -> Effective | None:
    """The connection and model the person uses, or None: then no `ai.use`."""
    return judge(await AssignmentRepository(session, org_id).resolve(user_id))


async def personal_agents_allowed(session: AsyncSession, org_id: uuid.UUID) -> bool:
    """The organisation's switch for personal agents (on unless an admin turned it
    off); with `ai.use` it gives `agent.create_personal`."""
    return await AssignmentRepository(session, org_id).personal_agents()
