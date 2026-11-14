"""The wiki's writing tools (plan M6 decisions 3, 8, 9; spec 8.6 and 9).

- `propose_page_change` (level 2): a proposal for a page's new content, decided by a
  moderator (`modules/proposals`); `propose_new_page` (level 2): a proposal for a new
  page. Both need `page.edit` in the page's space for the run (a proposal is what the
  person and the agent could have written themselves; stricter than reading), and the
  page as AI may read it (`no_ai` or policy `none`: not found).
- `update_page` (level 3), in two steps: the first call returns the diff against the
  page as it is now and a `token` bound to the run, the page, its version, its
  content and the new content; the second call, with that token, writes, unless the
  page changed meanwhile (then the diff anew). Only in spaces with
  `agent_write_policy=direct` (elsewhere it tells the model to propose), never into a
  page locked for AI (checked again under the page's row lock). Written as a Markdown
  save (`PageService.update`): the page's newest version holds its content before the
  write (every save is a version), the write is a new version with source `agent`,
  the agent as author and the run, and a new generation ends live sessions.

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
from app.modules.agents.toolbox.base import NOT_FOUND, ToolContext
from app.modules.agents.toolbox.writing import LEAKS, by, effect, leaks_into, refused
from app.modules.proposals.models import MAX_REASON_CHARS
from app.modules.proposals.service import ProposalService
from app.modules.wiki import diffing
from app.modules.wiki.models import MAX_CONTENT_CHARS, MAX_TITLE_CHARS, Page, VersionSource
from app.modules.wiki.service import PageService
from app.modules.wiki.visibility import PageReader
from app.runtime.loop import ToolResult

Content = Annotated[str, StringConstraints(min_length=1, max_length=MAX_CONTENT_CHARS)]
Reason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_REASON_CHARS)
]
DIFF_LINES = 400  # shown to the model at most; the token binds the whole content
PROPOSE_INSTEAD = "This space takes changes from agents only as proposals: use propose_page_change."


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


async def propose_page_change(ctx: ToolContext, args: ProposePageChangeArgs) -> ToolResult:
    attrs = {"page": str(args.page_id)}
    page = await _page(ctx, args.page_id)
    if page is None or not await can(ctx.session, ctx.actor, Action.PAGE_EDIT, page.space_id):
        return ToolResult("wiki", NOT_FOUND if page is None else "Not allowed here.", attrs)
    if await leaks_into(ctx, page.space_id):
        return ToolResult("wiki", LEAKS, attrs)

    async def write() -> ToolResult:
        proposal = await ProposalService(ctx.session).propose_change(
            ctx.actor,
            page.id,
            args.content_md,
            args.reason,
            author=by(ctx).principal,
            run_id=ctx.run.id,
        )
        text = f"Proposal id={proposal.id} made for page id={page.id}; a moderator decides."
        return ToolResult("wiki", text, attrs)

    return await effect(ctx, "wiki", attrs, write)


async def propose_new_page(ctx: ToolContext, args: ProposeNewPageArgs) -> ToolResult:
    attrs = {"space": str(args.space_id)}
    if not await can(ctx.session, ctx.actor, Action.PAGE_EDIT, args.space_id):
        return ToolResult("wiki", NOT_FOUND, attrs)
    if await leaks_into(ctx, args.space_id):
        return ToolResult("wiki", LEAKS, attrs)

    async def write() -> ToolResult:
        proposal = await ProposalService(ctx.session).propose_new(
            ctx.actor,
            args.space_id,
            args.parent_id,
            args.title,
            args.content_md,
            args.reason,
            author=by(ctx).principal,
            run_id=ctx.run.id,
        )
        return ToolResult("wiki", f"Proposal id={proposal.id} made; a moderator decides.", attrs)

    return await effect(ctx, "wiki", attrs, write)


async def update_page(ctx: ToolContext, args: UpdatePageArgs) -> ToolResult:
    attrs = {"page": str(args.page_id)}
    page = await _page(ctx, args.page_id)
    if page is None:
        return ToolResult("wiki", NOT_FOUND, attrs)
    if not await ProposalService(ctx.session).agent_writes_directly(ctx.actor, page.space_id):
        return ToolResult("wiki", PROPOSE_INSTEAD, attrs)
    if not await can(ctx.session, ctx.actor, Action.PAGE_EDIT, page.space_id):
        return ToolResult("wiki", "Not allowed here.", attrs)
    if await leaks_into(ctx, page.space_id):
        return ToolResult("wiki", LEAKS, attrs)
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
            source=VersionSource.AGENT,
            by=by(ctx),
        )
        return ToolResult("wiki", f"Page id={written.id} saved (version {written.version}).", attrs)

    return await effect(ctx, "wiki", attrs, write)


async def _page(ctx: ToolContext, page_id: uuid.UUID) -> Page | None:
    try:
        return await PageReader(ctx.session).for_ai(ctx.actor, page_id)
    except NotFound:
        return None


def _token(ctx: ToolContext, page: Page, content_md: str) -> str:
    """Binds a preview to the run, the page as it is (version and content) and the new
    content: a write with it changes exactly what the diff showed."""
    parts = (
        str(ctx.run.id),
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
