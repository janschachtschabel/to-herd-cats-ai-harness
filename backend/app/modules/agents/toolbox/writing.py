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
- **Drafts** (review M6 2 finding 1; spec 5.6): a run that read a draft of space X
  (`Reads.drafts`, or a page it read that is a draft now) writes nothing that people
  other than X's editors may read: every writing tool refuses (`DRAFTS`), except a
  proposal for a page of X (seen with `page.edit` in X), `update_page` on a draft of
  X, and what goes to the run's own conversation (`post_message` there, a question,
  the final answer): its audience reads the answer anyway, and it is either the
  person alone with the agent, who read the draft, or a draft's thread in X, which
  only X's editors read.
- **AI policy**: no tool writes into a space whose AI policy is `none`; every tool
  that names a space asks `closed_to_ai` first and answers "not found", as for a
  space it cannot see (review M6 finding 5). Tools that name a page or a ticket do
  not find one there (`PageReader.for_ai`, `reading.ticket_scope`).
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
from app.modules.agents.scope import organisation_audience, space_audience
from app.modules.agents.toolbox.base import NOT_FOUND, ToolContext
from app.modules.ai.models import AiPolicy
from app.runtime.loop import ToolResult

LEAKS = (
    "Not allowed: what you have read in this run may not be shown to the people of that "
    "space. Write only what comes from that space (or from open spaces)."
)
DRAFTS = (
    "Not allowed: you have read a draft in this run, and drafts are only for the editors "
    "of their space. Write nothing others may read; propose a change to a page of the "
    "draft's space instead, or answer here."
)


def by(ctx: ToolContext) -> Authorship:
    """What the tool writes is written for the agent, naming the run."""
    return Authorship(Principal.agent(ctx.run.agent_id), ctx.run.id)


def key_for(ctx: ToolContext, name: str, *parts: object) -> uuid.UUID:
    """A stable key for what a tool call writes (a message's `client_id`), from the
    run and the call's arguments."""
    return uuid.uuid5(ctx.run.id, ":".join([name, *map(str, parts)]))


async def closed_to_ai(ctx: ToolContext, space_id: uuid.UUID) -> bool:
    """Whether the space's AI policy is `none` (no tool writes there)."""
    policies = await ReadRepository(ctx.session, ctx.run.org_id).policies({space_id})
    return any(p.kind == AiPolicy.NONE for p in policies)


async def leaks_into(
    ctx: ToolContext, space_id: uuid.UUID, *, editors_only: bool = False
) -> str | None:
    """Why writing into the space would show its audience what it may not see (None:
    it would not): a draft read (`carries_draft`; `editors_only`: what is written
    there is read only by the space's editors), or a space read so far (where it was
    read, or where its page or ticket is now) outside the space's audience."""
    if why := await carries_draft(ctx, space_id if editors_only else None):
        return why
    read = await _read(ctx)
    if read and not read <= await space_audience(ctx.session, ctx.run.org_id, space_id):
        return LEAKS
    return None


async def leaks_into_organisation(ctx: ToolContext) -> str | None:
    """The same for what everyone of the organisation reads (an organisation-wide
    skill): a draft, or anything read outside the open spaces."""
    if why := await carries_draft(ctx):
        return why
    read = await _read(ctx)
    if read and not read <= await organisation_audience(ctx.session, ctx.run.org_id):
        return LEAKS
    return None


async def carries_draft(ctx: ToolContext, editors_of: uuid.UUID | None = None) -> str | None:
    """`DRAFTS` while the run holds a draft, unless every draft it read is of
    `editors_of`, the space whose editors alone read what is written."""
    drafts = await drafts_read(ctx)
    if drafts and not (editors_of is not None and drafts <= {editors_of}):
        return DRAFTS
    return None


async def drafts_read(ctx: ToolContext) -> set[uuid.UUID]:
    """The spaces of drafts the run read: noted when read, and pages it read that
    are drafts now."""
    now = await ReadRepository(ctx.session, ctx.run.org_id).draft_spaces(ctx.reads.pages)
    return ctx.reads.drafts | now


async def _read(ctx: ToolContext) -> set[uuid.UUID]:
    now = await ReadRepository(ctx.session, ctx.run.org_id).now(ctx.reads)
    return ctx.reads.spaces | now.spaces


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
