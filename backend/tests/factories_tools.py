"""A tool's context as a run gives it (`agents/toolbox/base.py`), for calling a tool
directly: the run's actor in a conversation (Alice's DM with the agent unless named),
the connection's data location, fresh reads, and a run reference."""

import uuid
from typing import Any

from app.modules.agents.actor import Reads, run_actor
from app.modules.agents.toolbox.base import RunRef, ToolContext
from app.modules.ai.models import DataLocation
from tests.factories_agents import Bench


async def tool_context(
    bench: Bench,
    conversation_id: object | None = None,
    *,
    who: str = "alice",
    run_id: uuid.UUID | None = None,
) -> ToolContext:
    user = bench.people.users[who]
    conversation = uuid.UUID(str(conversation_id or bench.dm_id))
    org = bench.agent.org_id
    actor = await run_actor(bench.session, org, user.id, bench.agent.id, conversation)
    assert actor is not None
    ref = RunRef(run_id or uuid.uuid4(), org, bench.agent.id, user.id, conversation)
    location = DataLocation(bench.connection.data_location)
    return ToolContext(bench.session, actor, location, Reads(), ref)


def call(name: str, **arguments: Any) -> dict[str, Any]:
    """A stub reply that calls one tool."""
    return {"tool_calls": [{"name": name, "arguments": arguments}]}
