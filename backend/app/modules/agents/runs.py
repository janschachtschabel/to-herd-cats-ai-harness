"""A run and its events as people read them (spec 8.3; the run view itself comes with
M6). A run is visible to the person who asked and to the agent's responsible person,
each while they have `ai.use`, and to holders of `agent.manage`; to anyone else it
answers 404 `run.not_found`, as for an unknown id.

What of the events (spec 5.5; module review 1, finding 1): the person who asked reads
their run in full. Anyone else reads
- a tool result only while they may read every space it came from (its `spaces`); an
  admin who reads such a space by admin right is noted (`space.admin_access`), as for
  a direct page read; otherwise, and for a result without noted spaces, the event
  comes `redacted`: its step, tool name and source stay;
- never the model's own words, its text and its tool calls' arguments, nor a tool
  call's arguments: they are the conversation's content, which its person reads (an
  admin only through the audited inspection of the DM). Usage, model, tool names and
  the stop stay.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, require
from app.core.errors import NotFound
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.agents.models import EventKind, Run, RunEvent
from app.modules.agents.run_repository import RunRepository

MODEL_CALL_SHOWN = ("step", "model", "tokens_in", "tokens_out", "tokens_cached", "duration_ms")
TOOL_CALL_SHOWN = ("step", "call_id", "name", "source")


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
        shown = [
            ShownEvent(e, e.content, False) if asker else await self._for_other(actor, e)
            for e in page.items
        ]
        return Page[ShownEvent](items=shown, next_cursor=page.next_cursor)

    async def _for_other(self, actor: Actor, event: RunEvent) -> ShownEvent:
        content = event.content
        if event.kind == EventKind.MODEL_CALL:
            kept = _pick(content, MODEL_CALL_SHOWN)
            calls = content.get("tool_calls") or []
            kept["tool_calls"] = [{"id": c.get("id"), "name": c.get("name")} for c in calls]
            return ShownEvent(event, kept, True)
        if event.kind == EventKind.TOOL_CALL:
            kept = _pick(content, TOOL_CALL_SHOWN)
            if not await self._may_read_all(actor, content.get("spaces")):
                return ShownEvent(event, kept, True)
            attrs = {k: v for k, v in (content.get("attrs") or {}).items() if k != "query"}
            return ShownEvent(event, {**kept, "attrs": attrs, "text": content.get("text")}, False)
        return ShownEvent(event, content, False)

    async def _may_read_all(self, actor: Actor, spaces: object) -> bool:
        """Whether the actor may read every one of the spaces now (none noted: no);
        `require` notes an admin's read by admin right."""
        if not isinstance(spaces, list) or not spaces:
            return False
        ids = [uuid.UUID(str(s)) for s in spaces]
        for space_id in ids:
            if not await can(self.session, actor, Action.SPACE_READ, space_id):
                return False
        for space_id in ids:
            await require(self.session, actor, Action.SPACE_READ, space_id)
        return True


def _pick(content: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: content[key] for key in keys if key in content}
