"""A run and its events as people read them (spec 8.3; the run view, its lists and
cancelling: `run_view.py`). A run is visible to the person who asked and to the
agent's responsible person, each while they have `ai.use`, and to holders of
`agent.manage`; to anyone else it answers 404 `run.not_found`, as for an unknown id.

What of the events (spec 5.5; module review 1, finding 1): the person who asked reads
their run in full. Anyone else reads
- a tool result only while they may read every space it came from (its `spaces`); an
  admin who reads such a space by admin right is noted (`space.admin_access`), as for
  a direct page read; otherwise, and for a result without noted spaces, the event
  comes `redacted`: its step, tool name and source stay; so does a result that
  marks itself the asker's (`ASKER_ONLY` in its attrs: `search_past_runs` with any
  of the model's words or a hit from a run that read no space, review M6 finding 10),
  and one that read a draft (its `read.drafts`) unless they see drafts in that space
  (`page.edit`, review M6 2 finding 2); and every tool result of a run that carries
  the personal mark (`RunRepository.marked`: what its asker read through her own
  connector, or a hit or a history that held it), from its first event on, whatever
  spaces it noted: its words may repeat what she read (module review M8 3, H1);
- an event of a kind this release does not know (a newer release wrote it during a
  rolling upgrade): left out, for everyone (module review M8 3, H6);
- never the model's own words, its text and its tool calls' arguments, nor a tool
  call's arguments: they are the conversation's content, which its person reads (an
  admin only through the audited inspection of the DM). Usage (tokens, cost,
  duration), model, tool names and the stop stay.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, require, sees_drafts
from app.core.errors import NotFound
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.agents.run_models import EventKind, Run, RunEvent
from app.modules.agents.run_repository import RunRepository

MODEL_CALL_SHOWN = (
    "step",
    "model",
    "tokens_in",
    "tokens_out",
    "tokens_cached",
    "duration_ms",
    "cost",
)
TOOL_CALL_SHOWN = ("step", "call_id", "name", "source", "duration_ms")
ASKER_ONLY = "asker_only"  # a tool result's attr: only the asker reads its text
# The kinds this release shows; another (a newer release's, during a rolling upgrade)
# is passed over, never a 500 (module review M8 3, H6).
KNOWN_KINDS = frozenset(kind.value for kind in EventKind)


def run_not_found() -> NotFound:
    return NotFound(code="run.not_found")


@dataclass(frozen=True, slots=True)
class ShownEvent:
    event: RunEvent
    content: dict[str, Any]
    redacted: bool


class RunService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, actor: Actor, run_id: uuid.UUID) -> Run:
        found = await RunRepository(self.session, actor.org_id).get(run_id)
        if found is None:
            raise run_not_found()
        run, agent = found
        if await can(self.session, actor, Action.AGENT_MANAGE):
            return run
        involved = actor.principal.id in (run.user_id, agent.responsible_user_id)
        if involved and await can(self.session, actor, Action.AI_USE):
            return run
        raise run_not_found()

    async def events(self, actor: Actor, run_id: uuid.UUID, params: PageParams) -> Page[ShownEvent]:
        """The run's events, in the order they happened, as the actor may read them."""
        run = await self.get(actor, run_id)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await RunRepository(self.session, actor.org_id).events(
            run.id, after, params.limit + 1
        )
        page = id_page(rows, params.limit, lambda e: e.id)
        asker = actor.principal.id == run.user_id
        repo = RunRepository(self.session, actor.org_id)
        marked = not asker and await repo.marked(run.id)  # hers alone, the whole run
        known = [e for e in page.items if e.kind in KNOWN_KINDS]  # a newer release's: passed
        shown = [
            ShownEvent(e, e.content, False)
            if asker
            else await self._for_other(actor, e, marked=marked)
            for e in known
        ]
        return Page[ShownEvent](items=shown, next_cursor=page.next_cursor)

    async def _for_other(self, actor: Actor, event: RunEvent, *, marked: bool) -> ShownEvent:
        content = event.content
        if event.kind == EventKind.MODEL_CALL:
            kept = _pick(content, MODEL_CALL_SHOWN)
            calls = content.get("tool_calls") or []
            kept["tool_calls"] = [{"id": c.get("id"), "name": c.get("name")} for c in calls]
            return ShownEvent(event, kept, True)
        if event.kind == EventKind.TOOL_CALL:
            kept = _pick(content, TOOL_CALL_SHOWN)
            attrs = {k: v for k, v in (content.get("attrs") or {}).items() if k != "query"}
            hidden = marked or attrs.get(ASKER_ONLY) or not await self._may_read_all(actor, content)
            if hidden:
                return ShownEvent(event, kept, True)
            return ShownEvent(event, {**kept, "attrs": attrs, "text": content.get("text")}, False)
        return ShownEvent(event, content, False)

    async def _may_read_all(self, actor: Actor, content: dict[str, Any]) -> bool:
        spaces = content.get("spaces")
        if not isinstance(spaces, list):
            return False
        drafts = (content.get("read") or {}).get("drafts") or []
        if not await may_read_drafts(self.session, actor, {uuid.UUID(str(d)) for d in drafts}):
            return False
        return await may_read_all(self.session, actor, {uuid.UUID(str(s)) for s in spaces})


async def may_read_all(session: AsyncSession, actor: Actor, spaces: set[uuid.UUID]) -> bool:
    """The redaction rule of run events: whether the actor may read every one of the
    spaces a result came from now (none noted: no); `require` notes an admin's read
    by admin right. Also what `search_past_runs` shows (`toolbox/past_runs.py`)."""
    if not spaces:
        return False
    ids = sorted(spaces)
    for space_id in ids:
        if not await can(session, actor, Action.SPACE_READ, space_id):
            return False
    for space_id in ids:
        await require(session, actor, Action.SPACE_READ, space_id)
    return True


async def may_read_drafts(session: AsyncSession, actor: Actor, spaces: set[uuid.UUID]) -> bool:
    """Whether the actor sees drafts in every one of the spaces (a result that read a
    draft there: run events, `search_past_runs`)."""
    for space_id in sorted(spaces):
        if not await sees_drafts(session, actor, space_id):
            return False
    return True


def _pick(content: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: content[key] for key in keys if key in content}
