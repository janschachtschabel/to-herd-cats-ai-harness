"""The wiki's writing tools (plan M6 decisions 3, 8, 9; spec 8.6 and 9).

- `propose_page_change` (level 2): a proposal for a page's new content, decided by a
  moderator (`modules/proposals`); `propose_new_page` (level 2): a proposal for a new
  page. Both need `page.edit` in the page's space for the run (a proposal is what the
  person and the agent could have written themselves; stricter than reading), and the
  page as AI may read it (`no_ai` or policy `none`: not found). Only the space's
  editors read a proposal, so after a draft read both go into that draft's space and
  no other (plan M9 task 8).
- `update_page` (level 3), in two steps: the first call returns the diff against the
  page as it is now and a `token` bound to the run, the page, its version, its
  content and the new content; the second call, with that token, writes, unless the
  page changed meanwhile (then the diff anew). Only in spaces with
  `agent_write_policy=direct` (elsewhere it tells the model to propose), never into a
  page locked for AI (checked again under the page's row lock). Written as a Markdown
  save (`PageService.update`): the page's newest version holds its content before the
  write (every save is a version), the write is a new version with source `agent`,
  the agent as author and the run, and a new generation ends live sessions. Never an
  agent's memory page: memory changes only through `update_memory`, which holds its
  rules (review M6 2, finding 3).

Nothing is deleted or put into the trash: no tool offers it. Every write goes through
`writing.effect` (one savepoint; the audience check of `writing.leaks_into` first).
"""

import asyncio
import hashlib
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.access import Action, can
from app.core.errors import NotFound
from app.modules.agents.memory_repository import MemoryRepository
from app.modules.agents.toolbox.base import (
    NOT_FOUND,
    CallContext,
    Subject,
    ToolContext,
    WriteContext,
)
from app.modules.agents.toolbox.writing import (
    by,
    closed_to_ai,
    effect,
    leaks_into,
    refusal,
    refused,
)
from app.modules.proposals.models import MAX_REASON_CHARS
from app.modules.proposals.service import ProposalService
from app.modules.wiki import diffing
from app.modules.wiki.models import (
    MAX_CONTENT_CHARS,
    MAX_TITLE_CHARS,
    Page,
    PageStatus,
)
from app.modules.wiki.service import PageService
from app.modules.wiki.visibility import PageReader
from app.runtime.loop import ToolResult

Content = Annotated[str, StringConstraints(min_length=1, max_length=MAX_CONTENT_CHARS)]
Reason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_REASON_CHARS)
]
DIFF_LINES = 400  # shown to the model at most; the token binds the whole content
PROPOSE_INSTEAD = "This space takes changes from agents only as proposals: use propose_page_change."
USE_UPDATE_MEMORY = "This is an agent's memory page: change your memory with update_memory."


class ProposePageChangeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: uuid.UUID
    content_md: Content
    reason: Reason


class ProposeNewPageArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_CHARS)
    ]
    content_md: Content
    reason: Reason


class UpdatePageArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: uuid.UUID
    content_md: Content
    reason: Reason
    token: Annotated[str, StringConstraints(max_length=64)] | None = None


async def propose_page_change(ctx: WriteContext, args: ProposePageChangeArgs) -> ToolResult:
    attrs = {"page": str(args.page_id)}
    page = await _page(ctx, args.page_id)
    if page is None or not await can(ctx.session, ctx.actor, Action.PAGE_EDIT, page.space_id):
        return refusal("wiki", NOT_FOUND if page is None else "Not allowed here.", attrs)
    if why := await leaks_into(ctx, page.space_id, editors_only=True):  # page.edit sees it
        return refusal("wiki", why, attrs)

    async def write() -> ToolResult:
        proposal = await ProposalService(ctx.session).propose_change(
            ctx.actor,
            page.id,
            args.content_md,
            args.reason,
            author=by(ctx).principal,
            run_id=by(ctx).run_id,
            via_token=by(ctx).via_token,
        )
        text = f"Proposal id={proposal.id} made for page id={page.id}; a moderator decides."
        return ToolResult("wiki", text, attrs)

    return await effect(ctx, "wiki", attrs, write)


async def propose_new_page(ctx: WriteContext, args: ProposeNewPageArgs) -> ToolResult:
    attrs = {"space": str(args.space_id)}
    if not await can(ctx.session, ctx.actor, Action.PAGE_EDIT, args.space_id) or (
        await closed_to_ai(ctx, args.space_id)
    ):
        return refusal("wiki", NOT_FOUND, attrs)
    # A proposal is read only with `page.edit` in its space: a draft of it may go in.
    if why := await leaks_into(ctx, args.space_id, editors_only=True):
        return refusal("wiki", why, attrs)

    async def write() -> ToolResult:
        proposal = await ProposalService(ctx.session).propose_new(
            ctx.actor,
            args.space_id,
            args.parent_id,
            args.title,
            args.content_md,
            args.reason,
            author=by(ctx).principal,
            run_id=by(ctx).run_id,
            via_token=by(ctx).via_token,
        )
        return ToolResult("wiki", f"Proposal id={proposal.id} made; a moderator decides.", attrs)

    return await effect(ctx, "wiki", attrs, write)


async def update_page(ctx: WriteContext, args: UpdatePageArgs) -> ToolResult:
    attrs = {"page": str(args.page_id)}
    page = await _page(ctx, args.page_id)
    if page is None:
        return refusal("wiki", NOT_FOUND, attrs)
    if await MemoryRepository(ctx.session, ctx.actor.org_id).is_memory(page.id):
        return refusal("wiki", USE_UPDATE_MEMORY, attrs)  # its rules: `memory_tools`
    if not await ProposalService(ctx.session).agent_writes_directly(ctx.actor, page.space_id):
        return refusal("wiki", PROPOSE_INSTEAD, attrs)
    if not await can(ctx.session, ctx.actor, Action.PAGE_EDIT, page.space_id):
        return refusal("wiki", "Not allowed here.", attrs)
    draft = page.status == PageStatus.DRAFT  # only the space's editors read it
    if why := await leaks_into(ctx, page.space_id, editors_only=draft):
        return refusal("wiki", why, attrs)
    ctx.reads.spaces.add(page.space_id)  # the diff shows the page
    ctx.reads.pages.add(page.id)
    spaces = frozenset({page.space_id})
    if page.content_md == args.content_md:
        return refused("wiki", "page.no_change", attrs)
    token = _token(ctx, page, args.content_md)
    if args.token != token:
        return ToolResult("wiki", await _preview(page, args.content_md, token), attrs, spaces)

    async def write() -> ToolResult:
        locked = await PageReader(ctx.session).repo(ctx.actor).live(page.id, lock=True)
        if locked is None or locked.no_ai:
            raise NotFound(code="page.not_found")
        if _token(ctx, locked, args.content_md) != token:  # changed since the check above
            return ToolResult("wiki", await _preview(locked, args.content_md, None), attrs, spaces)
        written = await PageService(ctx.session).update(
            ctx.actor,
            locked.id,
            content_md=args.content_md,
            version=locked.version,
            change_summary=args.reason,
            source=ctx.source,
            by=by(ctx),
        )
        return ToolResult("wiki", f"Page id={written.id} saved (version {written.version}).", attrs)

    return await effect(ctx, "wiki", attrs, write)


# --- what a call changes (a release is bound to it, `approvals/gate.py`) -------------


async def page_subjects(ctx: ToolContext, args: ProposePageChangeArgs) -> list[Subject] | None:
    page = await _page(ctx, args.page_id)
    return None if page is None else [_subject(page)]


async def new_page_subjects(ctx: ToolContext, args: ProposeNewPageArgs) -> list[Subject] | None:
    if not await can(ctx.session, ctx.actor, Action.PAGE_EDIT, args.space_id):
        return None
    subjects = [Subject("space", args.space_id, 0, args.space_id)]
    if args.parent_id is not None:
        parent = await _page(ctx, args.parent_id)
        if parent is None:
            return None
        subjects.append(_subject(parent))
    return subjects


async def update_subjects(ctx: ToolContext, args: UpdatePageArgs) -> list[Subject] | None:
    """Only the call with the preview's token writes; the preview changes nothing."""
    page = await _page(ctx, args.page_id)
    if page is None or args.token != _token(ctx, page, args.content_md):
        return None
    return [_subject(page)]


def _subject(page: Page) -> Subject:
    return Subject("page", page.id, page.version, page.space_id)


async def _page(ctx: CallContext, page_id: uuid.UUID) -> Page | None:
    try:
        return await PageReader(ctx.session).for_ai(ctx.actor, page_id)
    except NotFound:
        return None


def _token(ctx: WriteContext, page: Page, content_md: str) -> str:
    """Binds a preview to the writer (the run, or the token at `/mcp`), the page as it
    is (version and content) and the new content: a write with it changes exactly what
    the diff showed."""
    parts = (
        str(ctx.binding()),
        str(page.id),
        str(page.version),
        hashlib.sha256(page.content_md.encode()).hexdigest(),
        hashlib.sha256(content_md.encode()).hexdigest(),
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


async def _preview(page: Page, content_md: str, token: str | None) -> str:
    """The diff against the page now, and how to apply it."""
    found = await asyncio.to_thread(
        diffing.diff, page.title, page.content_md, page.title, content_md
    )
    lines: list[str] = []
    for hunk in found.hunks:
        mark = {"equal": " ", "delete": "-", "insert": "+"}[hunk.kind]
        shown = hunk.lines
        if hunk.kind == "equal" and len(shown) > 4:
            shown = [*shown[:2], "…", *shown[-2:]]
        lines += [f"{mark} {line}" for line in shown]
    if len(lines) > DIFF_LINES:
        lines = [*lines[:DIFF_LINES], "[… more changes not shown]"]
    head = f"Diff of page id={page.id} (version {page.version}) against your content:"
    if token is None:
        return (
            f"The page changed meanwhile. {head}\n"
            + "\n".join(lines)
            + ("\nCall update_page again without a token to get a new one.")
        )
    return (
        f"{head}\n"
        + "\n".join(lines)
        + (
            f"\nTo save exactly this, call update_page again with the same content, reason and "
            f'token="{token}".'
        )
    )
