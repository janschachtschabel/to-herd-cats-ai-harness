"""What every writing tool shares (plan M6 task 6).

- **Through the services, with the run's actor**: the person's rights held to the
  agent's roles and the place's read and write scope (`agents/actor.py`), so a tool
  writes only where the person and the agent both may, and only in the space of the
  run's task (`scope.py`). What a tool writes is written for the agent (`by`): its
  author is `agent:<id>`, with the run (`run_id`), and so are the change's events.
- **Audience** (review focus 1): a tool writes into a space only while everything the
  run has read so far came from a space whose content that space's audience may
  receive (`scope.space_audience`): the space itself, or the open spaces while it has
  no guest. A run that read a private space cannot carry it into another one.
- **One savepoint per effect**: a refusal of a service (`NotFound`, `Forbidden`,
  `Conflict`, `ValidationFailed`) undoes whatever the effect had written and becomes
  a tool error for the model (its code only, never content); the run goes on. The
  effect and the call's `run_event` commit together (`toolbox/base.py`), so a run
  taken up again never repeats it.
"""

import uuid
from collections.abc import Awaitable, Callable

from app.core.authorship import Authorship
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.principal import Principal
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.scope import space_audience
from app.modules.agents.toolbox.base import NOT_FOUND, ToolContext
from app.runtime.loop import ToolResult

LEAKS = (
    "Not allowed: what you have read in this run may not be shown to the people of that "
    "space. Write only what comes from that space (or from open spaces)."
)


def by(ctx: ToolContext) -> Authorship:
    """What the tool writes is written for the agent, naming the run."""
    return Authorship(Principal.agent(ctx.run.agent_id), ctx.run.id)


def key_for(ctx: ToolContext, name: str, *parts: object) -> uuid.UUID:
    """A stable key for what a tool call writes (a message's `client_id`), from the
    run and the call's arguments."""
    return uuid.uuid5(ctx.run.id, ":".join([name, *map(str, parts)]))


async def leaks_into(ctx: ToolContext, space_id: uuid.UUID) -> bool:
    """Whether writing into the space would show it what its audience may not see:
    a space read so far (where it was read, or where its page or ticket is now)
    outside the space's audience."""
    now = await ReadRepository(ctx.session, ctx.run.org_id).now(ctx.reads)
    read = ctx.reads.spaces | now.spaces
    if not read:
        return False
    return not read <= await space_audience(ctx.session, ctx.run.org_id, space_id)


def refused(source: str, code: str, attrs: dict[str, str] | None = None) -> ToolResult:
    return ToolResult(source, f"Refused ({code}).", attrs or {})


async def effect(
    ctx: ToolContext,
    source: str,
    attrs: dict[str, str],
    write: Callable[[], Awaitable[ToolResult]],
) -> ToolResult:
    """Run `write` in a savepoint; a service's refusal undoes it and is the result."""
    try:
        async with ctx.session.begin_nested():
            return await write()
    except NotFound:
        return ToolResult(source, NOT_FOUND, attrs)
    except Forbidden as exc:
        return ToolResult(source, f"Not allowed ({exc.code}).", attrs)
    except Conflict as exc:
        return ToolResult(source, f"Changed meanwhile ({exc.code}): read it again.", attrs)
    except ValidationFailed as exc:
        return refused(source, exc.code, attrs)
