"""The checks a run's step makes before it calls the model or a tool (`step_host.py`
drives them): the run is still this take-up's and not asked to stop, the tool still
granted, the person and the agent still allowed together, the policy of everything
read still met (for the model's connection, or an external tool's server), the daily
budgets not reached, the connection still there."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.modules.agents.actor import allowed_actor
from app.modules.agents.control_repository import ControlRepository
from app.modules.agents.executor_repository import RunSteps
from app.modules.agents.models import Agent
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.repository import AgentRepository
from app.modules.agents.run_models import (
    STEP_LOCK_TIMEOUT_SECONDS,
    STEP_STATEMENT_TIMEOUT_SECONDS,
    Run,
)
from app.modules.agents.toolbox.base import ToolSpec
from app.modules.agents.toolbox.policy import Grant, effective, watched
from app.modules.agents.working import Lost, Working
from app.modules.ai.budgets import budget_exhausted, has_price
from app.modules.ai.models import AiConnection, BudgetScope, DataLocation
from app.modules.ai.policy import ANY, connection_allowed, strictest
from app.runtime.loop import Halt


async def owned(
    session: AsyncSession, run: Working, statement: float = STEP_STATEMENT_TIMEOUT_SECONDS
) -> tuple[RunSteps, Run, Agent]:
    """The run's records, its row (locked) and its agent as now; the step's lock
    waits and statements bounded from its first statement on."""
    steps = RunSteps(session, run.claimed)
    await steps.limit_time(STEP_LOCK_TIMEOUT_SECONDS, statement)
    row = await steps.owned()
    if row is None:
        raise Lost
    if await ControlRepository(session, row.org_id).cancelled_by(row.id) is not None:
        raise Halt("cancelled")
    agent = await steps.agent()
    if agent is None:
        raise Halt("rights_revoked")
    run.agent = agent
    return steps, row, agent


async def granted(session: AsyncSession, run: Working, agent: Agent, spec: ToolSpec) -> Grant:
    """The tool is still allowed to the agent as it is now (level and entries):
    `allow`, or `confirm` (a person releases each call, `approvals/gate.py`; in an
    event rule's run every direct write, `policy.watched`)."""
    entries = await AgentRepository(session, agent.org_id).tool_entries(agent.id)
    entry = Grant(entries[spec.name]) if spec.name in entries else None
    grant = watched(effective(agent.level, spec, entry), spec, event_rule=run.event_rule)
    if grant == Grant.BLOCK:
        raise Halt("rights_revoked")
    return grant


async def run_actor_now(session: AsyncSession, run: Working, agent: Agent) -> Actor:
    claimed = run.claimed
    actor = await allowed_actor(
        session,
        claimed.org_id,
        claimed.user_id,
        agent,
        run.reads,
        claimed.conversation_id,
    )
    if actor is None:
        raise Halt("rights_revoked")
    return actor


async def check_policy(session: AsyncSession, run: Working, location: DataLocation) -> None:
    """The strictest current policy of every space read from, where it was read
    and where its page or ticket is now."""
    if not await policy_allows(session, run, location):
        raise Halt("policy_blocked")


async def policy_allows(session: AsyncSession, run: Working, location: DataLocation) -> bool:
    """Whether what the run read may go to `location` now (an external tool's server,
    plan M8 decision 8); a page read since locked for AI, trashed or deleted, or a
    ticket deleted, ends the run (`policy_blocked`) as before a model call."""
    repo = ReadRepository(session, run.claimed.org_id)
    now = await repo.now(run.reads)
    if now.blocked:
        raise Halt("policy_blocked")
    policy = strictest([ANY, *await repo.policies(run.reads.spaces | now.spaces)])
    return connection_allowed(location, policy)


async def exhausted(
    session: AsyncSession, run: Working, connection: AiConnection | None
) -> BudgetScope | None:
    """The daily budget of the organisation, the person or the agent that is
    reached, if one is; summed before the step locks the run's row, so the sum
    never holds a cancel or the lease's renewal (module review M7, finding 9)."""
    c = run.claimed
    priced = has_price(connection, run.model)
    return await budget_exhausted(session, c.org_id, c.user_id, c.agent_id, priced=priced)


async def location_of(steps: RunSteps, run: Working) -> DataLocation:
    connection = await steps.connection(run.connection_id)
    if connection is None:
        raise Halt("rights_revoked")
    return DataLocation(connection.data_location)
