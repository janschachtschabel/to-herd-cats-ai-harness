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
- **A person's own content** (the personal mark, `agents/personal_mark.py`; module
  review M8 2, G2): a run that holds what the asking person read through her own
  connector (`Reads.personal`, journaled) writes nothing others may read without her
  release: the checks note it (`release_first`, `ToolContext.owed`), and once nothing
  else refused the call (the draft mark, a leak, a space closed to AI, the tool's
  own refusals: module review M8 3, H3) `effect` raises `ReleaseFirst` right before
  the write and the host asks her to release exactly this call (`step_host.py`);
  after the release the call runs (`ToolContext.released`) and what it writes is
  not marked.
  A call the gate finds to change nothing (`update_page`'s preview under a `confirm`
  grant) runs without a release as `ToolContext.previewing`: `effect` never writes
  for it (module review M8 3, H1).
  The draft's exceptions do not spare a release. Its own conversation is open
  without a release only while the person is alone with the agent (`into_own`):
  elsewhere `post_message` there asks for the release too, while a question and the
  final answer are held back (`PERSONAL`).
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

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import write_limit
from app.core.authorship import Authorship
from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.modules.agents.actor import Reads
from app.modules.agents.personal_mark import ReleaseFirst
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.scope import PlaceKind, organisation_audience, place_of, space_audience
from app.modules.agents.toolbox.base import NOT_FOUND, CallContext, ToolContext, WriteContext
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
RELEASE_NEEDED = (
    "Not without the person's release: you have read something through the asking "
    "person's own connection in this run, and this call would write outside your "
    "conversation alone with her. Call it again to ask her to release exactly this."
)
PERSONAL = (
    "Not allowed here: you have read something through the asking person's own "
    "connection in this run, and it is for that person alone. Others read along here, "
    "so you cannot ask or answer here; answer only where you are alone with the person."
)


def by(ctx: WriteContext) -> Authorship:
    """For whom the tool writes: the run's agent (naming the run), or the person of a
    token at `/mcp` (with the token's name)."""
    return ctx.by


def key_for(ctx: WriteContext, name: str, *parts: object) -> uuid.UUID:
    """A key for what a tool call writes (a message's `client_id`): in a run stable,
    from the run and the call's arguments; at `/mcp` one per call."""
    return ctx.key(name, *parts)


async def closed_to_ai(ctx: CallContext, space_id: uuid.UUID) -> bool:
    """Whether the space's AI policy is `none` (no tool writes there)."""
    policies = await ReadRepository(ctx.session, ctx.actor.org_id).policies({space_id})
    return any(p.kind == AiPolicy.NONE for p in policies)


async def leaks_into(
    ctx: CallContext, space_id: uuid.UUID, *, editors_only: bool = False
) -> str | None:
    """Why writing into the space would show its audience what it may not see (None:
    it would not): a draft read (`editors_only`: what is written there is read only by
    the space's editors), or a space read so far (where it was read, or where its page
    or ticket is now) outside the space's audience. Then, under the personal mark, the
    person's release (`release_first`)."""
    if why := await _drafted(ctx, space_id if editors_only else None):
        return why
    read = await _read(ctx)
    if read and not read <= await space_audience(ctx.session, ctx.actor.org_id, space_id):
        return LEAKS
    release_first(ctx)
    return None


async def leaks_into_organisation(ctx: CallContext) -> str | None:
    """The same for what everyone of the organisation reads (an organisation-wide
    skill): a draft, or anything read outside the open spaces; then the release."""
    if why := await _drafted(ctx):
        return why
    read = await _read(ctx)
    if read and not read <= await organisation_audience(ctx.session, ctx.actor.org_id):
        return LEAKS
    release_first(ctx)
    return None


async def carries_draft(ctx: CallContext, editors_of: uuid.UUID | None = None) -> str | None:
    """`DRAFTS` while the run holds a draft, unless every draft it read is of
    `editors_of`, the space whose editors alone read what is written; then, under the
    personal mark, the person's release (`release_first`)."""
    if why := await _drafted(ctx, editors_of):
        return why
    release_first(ctx)
    return None


async def _drafted(ctx: CallContext, editors_of: uuid.UUID | None = None) -> str | None:
    drafts = await drafts_read(ctx)
    if drafts and not (editors_of is not None and drafts <= {editors_of}):
        return DRAFTS
    return None


def release_first(ctx: CallContext) -> None:
    """Under the personal mark, every write needs the asking person's release of this
    very call: noted here, asked by `effect` right before it writes (`ReleaseFirst`,
    which the host turns into a release). Whoever reads the place now, its audience
    can grow later, and what is written there carries no mark (module review M8 4, K1
    and K2): her personal space, a space only she belongs to, memory pages alike. The
    one place a marked run writes without it is its own conversation alone with her
    (`into_own`; that message is marked personal), where no tool calls this. Outside a
    run (`/mcp`) there is no mark."""
    if ctx.reads.personal and isinstance(ctx, ToolContext):
        ctx.owed.release = True


def _ask_release(ctx: CallContext) -> None:
    if isinstance(ctx, ToolContext) and ctx.owed.release and not ctx.released:
        raise ReleaseFirst


async def into_own(
    session: AsyncSession,
    reads: Reads,
    org_id: uuid.UUID,
    conversation_id: uuid.UUID,
    asker: uuid.UUID,
) -> str | None:
    """Why the run may not write into its own conversation (None: it may). A draft
    does not hold it back (its audience reads the answer anyway, see above); a result
    of the person's own connector does, unless the person is alone with the agent."""
    if not reads.personal:
        return None
    place = await place_of(session, org_id, conversation_id, asker)
    return None if place is not None and place.kind == PlaceKind.ALONE else PERSONAL


async def into_own_conversation(ctx: CallContext, conversation_id: uuid.UUID) -> str | None:
    """The same for a tool writing into the conversation it answers in, as the person
    its actor acts for."""
    actor = ctx.actor
    return await into_own(ctx.session, ctx.reads, actor.org_id, conversation_id, actor.principal.id)


async def drafts_read(ctx: CallContext) -> set[uuid.UUID]:
    """The spaces of drafts the run read: noted when read, and pages it read that
    are drafts now."""
    now = await ReadRepository(ctx.session, ctx.actor.org_id).draft_spaces(ctx.reads.pages)
    return ctx.reads.drafts | now


async def _read(ctx: CallContext) -> set[uuid.UUID]:
    now = await ReadRepository(ctx.session, ctx.actor.org_id).now(ctx.reads)
    return ctx.reads.spaces | now.spaces


async def _within_limit(ctx: CallContext) -> bool:
    writer = ctx.by.principal if isinstance(ctx, WriteContext) else ctx.actor.principal
    return await write_limit.admit_within(ctx.session, get_settings(), writer)


def refused(source: str, code: str, attrs: dict[str, str] | None = None) -> ToolResult:
    return ToolResult(source, f"Refused ({code}).", attrs or {}, failed=True)


def refusal(source: str, text: str, attrs: dict[str, str] | None = None) -> ToolResult:
    """A tool's answer that it did not write (not found, not allowed, a leak)."""
    return ToolResult(source, text, attrs or {}, failed=True)


async def effect(
    ctx: CallContext,
    source: str,
    attrs: dict[str, str],
    write: Callable[[], Awaitable[ToolResult]],
) -> ToolResult:
    """Run `write` in a savepoint; a service's refusal undoes it and is the result.
    Every write counts towards its writer's write limit (J10: the agent of a run on
    its own count, the person of a token at `/mcp`), in the step's transaction;
    beyond it the tool is refused (`rate.limited`) and writes nothing. Under the
    personal mark, a call whose checks noted a write others read asks the
    person's release first (`release_first`); one that runs unreleased because the
    gate found it to change nothing (`ToolContext.previewing`) never writes."""
    if isinstance(ctx, ToolContext) and ctx.previewing:
        return refusal(source, RELEASE_NEEDED, attrs)
    _ask_release(ctx)  # every other check passed: her release of exactly this
    if not await _within_limit(ctx):
        return refused(source, write_limit.CODE, attrs)
    try:
        async with ctx.session.begin_nested():
            return await write()
    except NotFound:
        return refusal(source, NOT_FOUND, attrs)
    except Forbidden as exc:
        return refusal(source, f"Not allowed ({exc.code}).", attrs)
    except Conflict as exc:
        return refusal(source, f"Changed meanwhile ({exc.code}): read it again.", attrs)
    except ValidationFailed as exc:
        return refused(source, exc.code, attrs)
