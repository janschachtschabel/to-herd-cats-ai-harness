"""Page proposals (spec 9, plan M6 decision 8): making them, reading them, withdrawing
them; deciding is in `decisions.py`. Who sees which: `repository.visible`.

Proposals are made through this service only (no public route in M6: people's
proposals, `human_review`, stay out until wanted). The caller names the author: an
agent (its run acts with the rights of the person who asked, `run_id` names the run)
or the acting person themselves. The actor must be able to read what the proposal is
about, as AI reads it when the author is an agent (`PageReader.for_ai`: not a page
locked for AI, not in a space whose AI policy is `none`); a page it cannot read is
404 `page.not_found`, as for an unknown id.
"""

import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require, space_ids_with, visible_space_ids
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.core.pagination import PageParams, decode_id_cursor, id_page
from app.core.principal import Principal, PrincipalType
from app.modules.ai.models import AiPolicy
from app.modules.messaging.agent_hooks import agent_hooks
from app.modules.proposals import merge, rules
from app.modules.proposals.events import PROPOSAL_CREATED, PROPOSAL_WITHDRAWN, proposal_event
from app.modules.proposals.models import (
    PageProposal,
    ProposalKind,
    ProposalState,
)
from app.modules.proposals.repository import ProposalFacts, ProposalRepository, ProposalScope
from app.modules.spaces.models import AgentWritePolicy
from app.modules.wiki import diffing
from app.modules.wiki.models import Page
from app.modules.wiki.visibility import PageReader


def proposal_not_found() -> NotFound:
    return NotFound(code="proposal.not_found")


@dataclass(frozen=True, slots=True)
class Detail:
    """A proposal with its diff (base → proposed; None when too large to compare) and,
    for an open change whose page moved on, the page's current content and version
    and the three-way merge (None when too large)."""

    proposal: PageProposal
    diff: diffing.Diff | None
    current_content_md: str | None
    page_version: int | None
    merged: merge.Merge | None


@dataclass(frozen=True, slots=True)
class Names:
    """For showing proposals: people's and agents' names, version numbers by id."""

    people: dict[uuid.UUID, str] = field(default_factory=dict)
    agents: dict[uuid.UUID, str] = field(default_factory=dict)
    versions: dict[uuid.UUID, int] = field(default_factory=dict)


class ProposalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = PageReader(session)

    def repo(self, actor: Actor, author: Principal | None = None) -> ProposalRepository:
        scope = ProposalScope(
            actor.org_id,
            visible_space_ids(actor),
            space_ids_with(actor, Action.PAGE_EDIT),
            author or actor.principal,
        )
        return ProposalRepository(self.session, scope)

    def facts(self, actor: Actor) -> ProposalFacts:
        return ProposalFacts(self.session, actor.org_id)

    # --- reading -------------------------------------------------------------------

    async def get(
        self,
        actor: Actor,
        proposal_id: uuid.UUID,
        *,
        lock: bool = False,
        author: Principal | None = None,
    ) -> PageProposal:
        proposal = await self.repo(actor, author).get(proposal_id, lock=lock)
        if proposal is None:
            raise proposal_not_found()
        return proposal

    async def list(
        self,
        actor: Actor,
        space_id: uuid.UUID,
        state: ProposalState | None,
        params: PageParams,
    ) -> pagination.Page[PageProposal]:
        """Newest first."""
        await require(self.session, actor, Action.SPACE_READ, space_id)
        before = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).page(space_id, state, before, params.limit + 1)
        return id_page(rows, params.limit, lambda p: p.id)

    async def detail(self, actor: Actor, proposal_id: uuid.UUID) -> Detail:
        proposal = await self.get(actor, proposal_id)
        base = proposal.base_content_md or ""
        diff = None
        if rules.fits(base, proposal.content_md):
            title = proposal.title or ""
            diff = await asyncio.to_thread(diffing.diff, title, base, title, proposal.content_md)
        current = page_version = merged = None
        if proposal.kind == ProposalKind.CHANGE and proposal.state == ProposalState.OPEN:
            assert proposal.page_id is not None
            page = await self.reader.repo(actor).live(proposal.page_id)
            if page is not None:
                page_version = page.version
                if page.content_md != base:
                    current = page.content_md
                    merged = await rules.merge_of(proposal, page)
        return Detail(proposal, diff, current, page_version, merged)

    async def names(self, actor: Actor, proposals: Sequence[PageProposal]) -> Names:
        """The names and numbers the proposals refer to (all of them visible to the
        actor with the proposals)."""
        facts = self.facts(actor)
        people = {p.decided_by_id for p in proposals if p.decided_by_id}
        people |= {p.author_id for p in proposals if p.author_type == PrincipalType.USER}
        agents = {p.author_id for p in proposals if p.author_type == PrincipalType.AGENT}
        versions = {p.result_version_id for p in proposals if p.result_version_id}
        return Names(
            people=await facts.user_names(people),
            agents=await agent_hooks().names(self.session, actor.org_id, agents) if agents else {},
            versions=await facts.version_numbers(versions),
        )

    async def agent_writes_directly(self, actor: Actor, space_id: uuid.UUID) -> bool:
        """Whether the space lets agents write its pages directly (`direct`) rather than
        propose (`propose`, the default); 404 for a space the actor cannot read."""
        await require(self.session, actor, Action.SPACE_READ, space_id)
        return await self.facts(actor).write_policy(space_id) == AgentWritePolicy.DIRECT

    # --- making and withdrawing ------------------------------------------------------

    async def propose_change(
        self,
        actor: Actor,
        page_id: uuid.UUID,
        content_md: str,
        reason: str,
        *,
        author: Principal,
        run_id: uuid.UUID | None = None,
    ) -> PageProposal:
        """A change of the page's content, based on its content now."""
        rules.check_author(actor, author)
        content_md, reason = rules.content(content_md), rules.reason(reason)
        page = await self._readable(actor, page_id, author)
        locked = await self.reader.repo(actor).live(page.id, lock=True)  # saves wait
        latest = await self.facts(actor).latest_version(page.id)
        if locked is None or latest is None:
            raise NotFound(code="page.not_found")
        if locked.content_md == content_md:
            raise ValidationFailed(code="proposal.no_change")
        proposal = PageProposal(
            org_id=actor.org_id,
            space_id=locked.space_id,
            kind=ProposalKind.CHANGE,
            page_id=locked.id,
            base_version=latest.number,
            base_content_md=locked.content_md,
            **rules.common(content_md, reason, author, run_id),
        )
        return await self._made(actor, proposal)

    async def propose_new(
        self,
        actor: Actor,
        space_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        title: str,
        content_md: str,
        reason: str,
        *,
        author: Principal,
        run_id: uuid.UUID | None = None,
    ) -> PageProposal:
        """A new page under `parent_id` (None: the top level) of the space."""
        rules.check_author(actor, author)
        content_md, reason = rules.content(content_md), rules.reason(reason)
        title = rules.title(title)
        await require(self.session, actor, Action.SPACE_READ, space_id)
        if parent_id is not None:
            parent = await self._readable(actor, parent_id, author)
            if parent.space_id != space_id:
                raise ValidationFailed(code="page.parent_not_found")
        elif author.type == PrincipalType.AGENT:
            if await self.facts(actor).ai_policy(space_id) == AiPolicy.NONE:
                raise NotFound(code="space.not_found")
        proposal = PageProposal(
            org_id=actor.org_id,
            space_id=space_id,
            kind=ProposalKind.NEW,
            parent_id=parent_id,
            title=title,
            **rules.common(content_md, reason, author, run_id),
        )
        return await self._made(actor, proposal)

    async def withdraw(
        self, actor: Actor, proposal_id: uuid.UUID, version: int, *, author: Principal
    ) -> PageProposal:
        """The author takes an open proposal back (an agent's run, or the person)."""
        rules.check_author(actor, author)
        proposal = await self.get(actor, proposal_id, lock=True, author=author)
        if (proposal.author_type, proposal.author_id) != (author.type, author.id):
            raise Forbidden(code="auth.permission_denied")
        rules.check_open(proposal, version)
        rules.decide(proposal, actor, ProposalState.WITHDRAWN)
        await self.session.flush()
        await proposal_event(self.session, actor, PROPOSAL_WITHDRAWN, proposal)
        return proposal

    async def _readable(self, actor: Actor, page_id: uuid.UUID, author: Principal) -> Page:
        if author.type == PrincipalType.AGENT:
            return await self.reader.for_ai(actor, page_id)
        return await self.reader.readable(actor, page_id)

    async def _made(self, actor: Actor, proposal: PageProposal) -> PageProposal:
        proposal = await self.repo(actor).add(proposal)
        await proposal_event(self.session, actor, PROPOSAL_CREATED, proposal)
        return proposal
