"""Accepting and rejecting proposals (spec 9, plan M6 decisions 8 and 9): with
`page.moderate` in the proposal's space, by a person (never an agent's run: an
actor with a `read_scope` gets 403), naming the proposal's `version` (409).

Accepting a change writes the page exactly as a Markdown save (`PageService.update`):
a new version with the reason as its change text, written for the author (an agent:
source `agent`, its run; `authorship.py`), and a new generation, so open live
sessions end. Accepted with a merged text (`merged_content`, the moderator's
confirmation or own resolution), the version is the moderator's (source `human`, no
run): the text is no longer the author's; the proposal links it (`result_version_id`).
Never into a page in the trash (409 `proposal.page_trashed`), never
into a page locked for AI when the author is an agent (409 `proposal.page_no_ai`).

The merge rule: when the page's content is still the base, the proposal applies as it
is. When it moved on, nothing is applied: 409 `proposal.base_outdated` carries the
page's current `version` and the three-way merge (`merged_content` when it merges
cleanly, else null; `segments`, the merge with its conflict regions; `too_large`
when the texts are beyond `HERD_DIFF_MAX_LINES`). The moderator then accepts again
with `merged_content` (the clean merge, or their own resolution) and that
`page_version`; a page that moved on once more is 409 `proposal.base_outdated`
again. So a merged text is always confirmed explicitly, and a conflict is never
resolved silently.

Accepting a new page creates it as a draft under its parent (which must still be
outside the trash: 409 `proposal.parent_gone`) with the moderator's rights.

Row locks: the proposal first, then the page; a page save, the trash and the AI lock
lock the page only, so they wait for or come before the decision, never between
its check and its write.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.core.errors import Conflict, Forbidden, ValidationFailed
from app.core.principal import Principal, PrincipalType
from app.modules.audit.recorder import record
from app.modules.proposals import merge
from app.modules.proposals.events import PROPOSAL_ACCEPTED, PROPOSAL_REJECTED, proposal_event
from app.modules.proposals.models import PageProposal, ProposalKind, ProposalState
from app.modules.proposals.rules import check_open, decide, merge_of
from app.modules.proposals.service import ProposalService
from app.modules.wiki.authorship import Authorship
from app.modules.wiki.models import Page, PageVersion, VersionSource
from app.modules.wiki.service import PageService


def author_of(proposal: PageProposal) -> Principal:
    return Principal(PrincipalType(proposal.author_type), proposal.author_id)


class ProposalDecisions:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.proposals = ProposalService(session)
        self.pages = PageService(session)

    async def accept(
        self,
        actor: Actor,
        proposal_id: uuid.UUID,
        version: int,
        *,
        merged_content: str | None = None,
        page_version: int | None = None,
    ) -> PageProposal:
        proposal = await self._decidable(actor, proposal_id, version)
        if proposal.kind == ProposalKind.CHANGE:
            written = await self._apply_change(actor, proposal, merged_content, page_version)
        else:
            written = await self._create_page(actor, proposal)
        decide(proposal, actor, ProposalState.ACCEPTED)
        if written is not None:
            proposal.page_id, proposal.result_version_id = written.page_id, written.id
        await self.session.flush()
        details = {"space_id": str(proposal.space_id), "page_id": str(proposal.page_id)}
        await record(self.session, actor, "proposal.accepted", "proposal", proposal.id, details)
        await proposal_event(self.session, actor, PROPOSAL_ACCEPTED, proposal)
        return proposal

    async def reject(
        self, actor: Actor, proposal_id: uuid.UUID, version: int, reason: str | None = None
    ) -> PageProposal:
        proposal = await self._decidable(actor, proposal_id, version)
        decide(proposal, actor, ProposalState.REJECTED, reason)
        await self.session.flush()
        details = {"space_id": str(proposal.space_id)}
        await record(self.session, actor, "proposal.rejected", "proposal", proposal.id, details)
        await proposal_event(self.session, actor, PROPOSAL_REJECTED, proposal)
        return proposal

    async def _decidable(self, actor: Actor, proposal_id: uuid.UUID, version: int) -> PageProposal:
        proposal = await self.proposals.get(actor, proposal_id, lock=True)
        await require(self.session, actor, Action.PAGE_MODERATE, proposal.space_id)
        if actor.read_scope is not None:  # an agent's run decides nothing
            raise Forbidden(code="auth.permission_denied")
        check_open(proposal, version)
        return proposal

    async def _apply_change(
        self,
        actor: Actor,
        proposal: PageProposal,
        merged_content: str | None,
        page_version: int | None,
    ) -> PageVersion | None:
        assert proposal.page_id is not None
        page = await self.proposals.reader.repo(actor).live(proposal.page_id, lock=True)
        if page is None:
            raise Conflict(code="proposal.page_trashed")
        author = author_of(proposal)
        if author.type == PrincipalType.AGENT and page.no_ai:
            raise Conflict(code="proposal.page_no_ai")
        if merged_content is None:
            if page.content_md != proposal.base_content_md:
                raise await _outdated(proposal, page)
            content = proposal.content_md
        else:
            if page_version != page.version:
                raise await _outdated(proposal, page)
            content = merged_content
        before = page.version
        merged = merged_content is not None  # the moderator's text: the moderator's version
        await self.pages.update(
            actor,
            page.id,
            content_md=content,
            version=page.version,
            change_summary=proposal.reason,
            source=VersionSource.HUMAN if merged else _source(author),
            by=None if merged else Authorship(author, proposal.run_id),
        )
        if page.version == before:  # the page holds this content already
            return None
        return await self.proposals.facts(actor).latest_version(page.id)

    async def _create_page(self, actor: Actor, proposal: PageProposal) -> PageVersion | None:
        assert proposal.title is not None
        author = author_of(proposal)
        try:
            page = await self.pages.create(
                actor,
                proposal.space_id,
                proposal.parent_id,
                proposal.title,
                proposal.content_md,
                source=_source(author),
                by=Authorship(author, proposal.run_id),
            )
        except ValidationFailed as exc:
            if exc.code == "page.parent_not_found":
                raise Conflict(code="proposal.parent_gone") from None
            raise
        return await self.proposals.facts(actor).latest_version(page.id)


def _source(author: Principal) -> VersionSource:
    return VersionSource.AGENT if author.type == PrincipalType.AGENT else VersionSource.HUMAN


async def _outdated(proposal: PageProposal, page: Page) -> Conflict:
    merged = await merge_of(proposal, page)
    details: dict[str, Any] = {
        "current_version": page.version,
        "too_large": merged is None,
        "merged_content": merged.text if merged else None,
        "segments": [_segment(s) for s in merged.segments] if merged else [],
    }
    return Conflict(code="proposal.base_outdated", details=details)


def _segment(segment: merge.Segment) -> dict[str, Any]:
    if segment.kind == "clean":
        return {"kind": "clean", "lines": segment.lines}
    return {
        "kind": "conflict",
        "base": segment.base,
        "proposed": segment.proposed,
        "current": segment.current,
    }
