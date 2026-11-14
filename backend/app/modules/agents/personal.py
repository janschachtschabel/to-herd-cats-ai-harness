"""Personal agents (plan M6 decision 13; spec 8.1): a person's own agents.

- **Who**: whoever holds `agent.create_personal` (derived: `ai.use` while the
  organisation allows personal agents, `core/access.py`) creates them; with `ai.use`
  but the switch off: 403 `agent.personal_disabled`; without `ai.use`: 404
  `agent.not_found`. The owner manages their own agents (read, change, pause, delete
  if unused, tools) while they have `ai.use`; `agent.manage` manages all agents.
- **Owner and responsible**: the owner is the responsible person (another one: 422
  `agent.responsible_invalid`), and is billed: only the owner talks to the agent, so
  every run asks as the owner.
- **Connection and model**: the owner's assignment (`ai/effective.py`), taken anew with
  every change (while the owner has AI); given ones must be those (422 `ai.connection_not_found`,
  `ai.model_unknown`). While the owner's assignment differs, the agent does not run
  (`agent.connection_unavailable`, `standing.py`) until it is saved again.
- **Level**: at most 2 (403 `agent.level_denied`), also when an admin sets it.
- **Spaces**: a member (`editor`) of its owner's personal space only, from its creation;
  adding it to any other space is refused (422 `agent.personal_space_only`; to
  someone who may not see it: 404 `agent.not_found`).
- **Limit**: `HERD_AI_PERSONAL_AGENTS_MAX` per person (409 `agent.personal_limit`),
  counted under a lock per person, so two creations at once cannot pass it.
- **Admins**: they see every agent in the administration; being shown someone else's
  personal agent (the list, opening it, its runs) is audited (`agent.admin_access`,
  once per admin, agent and UTC day). Everywhere else (DM, profile, directory,
  mentions) only its owner reaches it (`standing.py`, `directory`).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, ValidationFailed
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.core.repository import advisory_xact_lock
from app.modules.agents.models import Agent
from app.modules.agents.repository import AgentRepository
from app.modules.agents.standing import agent_not_found
from app.modules.agents.toolbox.policy import FREE_LEVEL
from app.modules.ai.effective import Effective, effective_assignment
from app.modules.audit.recorder import record_agent_admin_access
from app.modules.spaces.repository import SpaceRepository

PERSONAL_ROLE = SpaceRole.EDITOR


async def require_personal_right(session: AsyncSession, actor: Actor) -> None:
    """The right to create one's own agents (see above for the answers without)."""
    if await can(session, actor, Action.AGENT_CREATE_PERSONAL):
        return
    if await can(session, actor, Action.AI_USE):
        raise Forbidden(code="agent.personal_disabled")
    raise agent_not_found()


async def may_manage(session: AsyncSession, actor: Actor, agent: Agent) -> bool:
    """`agent.manage`, or the agent's owner with `ai.use`."""
    if await can(session, actor, Action.AGENT_MANAGE):
        return True
    return agent.owner_user_id == actor.principal.id and await can(session, actor, Action.AI_USE)


async def owners_target(
    session: AsyncSession, org_id: uuid.UUID, owner: uuid.UUID
) -> Effective | None:
    """The owner's connection and model now (None: the owner has no AI; then an
    admin may still change the agent, but not its connection or model)."""
    return await effective_assignment(session, org_id, owner)


def check_given(
    target: Effective | None,
    owner: uuid.UUID,
    *,
    connection_id: uuid.UUID | None,
    model: str | None,
    responsible_user_id: uuid.UUID | None,
    level: int | None,
) -> None:
    """What a personal agent may be given: only its owner's (see above)."""
    if connection_id is not None and (target is None or connection_id != target.connection_id):
        raise ValidationFailed(code="ai.connection_not_found")
    if model is not None and (target is None or model != target.model):
        raise ValidationFailed(code="ai.model_unknown")
    if responsible_user_id is not None and responsible_user_id != owner:
        raise ValidationFailed(code="agent.responsible_invalid")
    if level is not None and level > FREE_LEVEL:
        raise Forbidden(code="agent.level_denied")


async def within_limit(session: AsyncSession, org_id: uuid.UUID, owner: uuid.UUID) -> None:
    """Room for one more of the owner's agents; held until the transaction ends."""
    await advisory_xact_lock(session, f"agent.personal:{owner}")
    owned = await AgentRepository(session, org_id).count_owned(owner)
    if owned >= get_settings().ai_personal_agents_max:
        raise Conflict(code="agent.personal_limit")


async def join_home(session: AsyncSession, agent: Agent) -> None:
    """The new personal agent becomes a member of its owner's personal space."""
    assert agent.owner_user_id is not None
    spaces = SpaceRepository(session)
    home = await spaces.get_personal(agent.org_id, agent.owner_user_id)
    if home is None:  # every person has one (`SpaceService.create_personal`)
        raise Conflict(code="agent.personal_space_missing")
    await spaces.set_member(home.id, Principal.agent(agent.id), PERSONAL_ROLE)


async def note_admin_access(session: AsyncSession, actor: Actor, agents: Sequence[Agent]) -> None:
    """Audit an admin shown someone else's personal agents (owners see their own)."""
    others = [a.id for a in agents if a.owner_user_id not in (None, actor.principal.id)]
    if others:
        await record_agent_admin_access(session, actor, others)
