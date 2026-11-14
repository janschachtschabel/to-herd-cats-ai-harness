"""`search_past_runs` (spec 8.5, plan M6 task 4): text in this agent's earlier runs
for the person who asks now, never another person's, never the run itself.

It shows only what the current run may read now, by the redaction rule of the run
view (`runs.may_read_all`), applied in the statement and again for each hit (which
also notes an admin's read by admin right):
- a tool result while every space it came from is readable now and its policy lets
  the run's connection receive it (a result that noted no space: never);
- the model's own words (its text, a final result) while every space its run read is,
  as they may repeat any of it;
- what a hit read counts for the run's checks like a fresh read: its spaces and its
  pages and tickets where they are now (a page locked or trashed since: no hit).
The result is the asker's alone in the run view (`runs.ASKER_ONLY`) once a hit holds
the model's words or comes from a run that noted no space (or from such a result):
the model's words are the conversation's content, which the run view shows nobody
else, whatever spaces the other hits came from (review M6 finding 10).
Outside a DM of the person alone with the agent, only runs of the same conversation:
another conversation's audience is not this one's (plan M6 decision 5). A run whose
conversation the person no longer sees is left out too.
"""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.access import visible_space_ids
from app.core.errors import NotFound
from app.modules.agents.actor import Reads
from app.modules.agents.models import EventKind
from app.modules.agents.past_runs_repository import (
    PastHit,
    PastRunRepository,
    RunReads,
    event_reads,
)
from app.modules.agents.read_repository import ReadRepository
from app.modules.agents.runs import ASKER_ONLY, may_read_all
from app.modules.agents.scope import PlaceKind, place_of
from app.modules.agents.toolbox.base import NOT_FOUND, ToolContext
from app.modules.ai.policy import ANY, connection_allowed, strictest
from app.modules.ai.policy_filters import ai_space_ids
from app.modules.messaging.service import ConversationService
from app.modules.spaces.models import Space
from app.runtime.loop import ToolResult

HITS = 5
CANDIDATES = 50
AROUND = 200  # characters of a hit's text on each side of the match


class SearchPastRunsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


async def search_past_runs(ctx: ToolContext, args: SearchPastRunsArgs) -> ToolResult:
    run = ctx.run
    place = await place_of(ctx.session, run.org_id, run.conversation_id, run.user_id)
    if place is None:
        return ToolResult("past_runs", NOT_FOUND)
    readable = visible_space_ids(ctx.actor).where(
        Space.id.in_(ai_space_ids(run.org_id, ctx.location))
    )
    repo = PastRunRepository(ctx.session, run.org_id)
    hits = await repo.search(
        agent_id=run.agent_id,
        user_id=run.user_id,
        exclude=run.id,
        text=args.query,
        readable=readable,
        conversation_id=None if place.kind == PlaceKind.ALONE else run.conversation_id,
        limit=CANDIDATES,
    )
    of_runs = await repo.reads(h.run_id for h in hits if _words(h))
    checker = _Checker(ctx)
    lines: list[str] = []
    spaces: set[uuid.UUID] = set()
    private = False
    for hit in hits:
        noted = of_runs[hit.run_id] if _words(hit) else event_reads(hit.content)
        now = await checker.readable(hit, noted)
        if now is None:
            continue
        spaces |= now
        private |= _words(hit) or not now or bool((hit.content.get("attrs") or {}).get(ASKER_ONLY))
        ctx.reads.spaces |= now
        ctx.reads.pages |= noted.pages
        ctx.reads.tickets |= noted.tickets
        lines.append(_line(hit, args.query))
        if len(lines) == HITS:
            break
    attrs = {ASKER_ONLY: "true"} if private else {}
    return ToolResult("past_runs", "\n".join(lines) or NOT_FOUND, attrs, frozenset(spaces))


class _Checker:
    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx
        self.conversations: dict[uuid.UUID, bool] = {}

    async def readable(self, hit: PastHit, noted: RunReads) -> set[uuid.UUID] | None:
        """The spaces the hit counts as read from now, if the run may read it."""
        ctx = self.ctx
        if not await self._sees(hit.conversation_id):
            return None
        repo = ReadRepository(ctx.session, ctx.run.org_id)
        now = await repo.now(Reads(pages=set(noted.pages), tickets=set(noted.tickets)))
        if now.blocked:
            return None
        spaces = noted.spaces | now.spaces
        if not _words(hit) and not noted.spaces:  # a result that noted no space: never
            return None
        if not spaces:
            return spaces
        if not connection_allowed(ctx.location, strictest([ANY, *await repo.policies(spaces)])):
            return None
        return spaces if await may_read_all(ctx.session, ctx.actor, spaces) else None

    async def _sees(self, conversation_id: uuid.UUID) -> bool:
        if conversation_id not in self.conversations:
            try:
                await ConversationService(self.ctx.session).get(self.ctx.actor, conversation_id)
                self.conversations[conversation_id] = True
            except NotFound:
                self.conversations[conversation_id] = False
        return self.conversations[conversation_id]


def _words(hit: PastHit) -> bool:
    """The model's own words: its text, or a final result."""
    return hit.kind == EventKind.MODEL_CALL or hit.content.get("final") is True


def _line(hit: PastHit, query: str) -> str:
    text = str(hit.content.get("text") or "")
    at = text.lower().find(query.lower())
    start, end = max(0, at - AROUND), at + len(query) + AROUND
    snippet = ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")
    what = "the agent's words" if _words(hit) else f"tool {hit.content.get('name')}"
    return f"- run {hit.run_id} at {hit.at:%Y-%m-%d %H:%M} ({what}):\n  {snippet}"
