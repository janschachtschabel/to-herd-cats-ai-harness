"""Skill proposals (plan M6 task 9): a new skill or a change to one, proposed by an
agent's run (`agents/toolbox/skill_tools.propose_skill`), decided by whoever may
manage skills in its scope. Who sees which: `sight.py`.

- **Proposing** (no route; the tool, or a person through this service): the actor
  must see skills (`base.gate`). A change names a skill the actor sees, active, and
  must change its description or content (422 `skill_proposal.no_change`); it keeps
  the number of the skill's newest version (`base_number`). A new skill names its
  scope (a space the actor reads, or the organisation) and a name free there (409
  `skill.name_taken`). In a space the actor needs `page.edit` (what it could write
  itself, as for page proposals; a run's write scope holds it); organisation-wide
  proposals need nothing more (they are decided by `skill.manage`). The author is
  an agent or the acting person (422 `skill_proposal.bad_author`).
- **Deciding** (`proposal_decisions.py`: `accept`, `reject`): a person who may
  manage skills in the scope (`base.may_manage`; 403 else; a run never decides), on
  an open proposal (409
  `skill_proposal.not_open`) at its `version` (409 `skill_proposal.version_conflict`).
- **Accepting a change**: if the skill has a newer version than `base_number`, 409
  `skill_proposal.base_outdated` with both texts and the skill's `version`, and
  nothing is written; the moderator accepts again with that `skill_version` and,
  where wanted, the final text. Accepting goes through `SkillService.update`: a new
  version authored by the proposal's author, or by the moderator when the final text
  differs from the proposal. An archived skill takes no change (409
  `skill_proposal.skill_archived`). Accepting a new skill is `SkillService.create`
  with the same rule for its author.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, decode_id_cursor, id_page
from app.core.principal import Principal, PrincipalType
from app.modules.skills import base
from app.modules.skills.models import Skill, SkillState
from app.modules.skills.proposal_events import (
    SKILL_PROPOSAL_CREATED,
    skill_proposal_event,
)
from app.modules.skills.proposal_models import (
    MAX_REASON_CHARS,
    SkillProposal,
    SkillProposalKind,
    SkillProposalState,
)
from app.modules.skills.proposal_repository import (
    SkillProposalFacts,
    SkillProposalFilter,
    SkillProposalRepository,
)
from app.modules.skills.proposal_schemas import Shown
from app.modules.skills.sight import sight_of


def not_found() -> NotFound:
    return NotFound(code="skill_proposal.not_found")


class SkillProposalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def repo(self, actor: Actor) -> SkillProposalRepository:
        return SkillProposalRepository(self.session, await sight_of(self.session, actor))

    # --- proposing -------------------------------------------------------------------

    async def propose_change(
        self,
        actor: Actor,
        skill_id: uuid.UUID,
        description: str,
        content: str,
        reason: str,
        *,
        author: Principal,
        run_id: uuid.UUID | None = None,
    ) -> SkillProposal:
        _check_author(actor, author)
        skill = await base.visible(self.session, actor, skill_id)
        if skill.state != SkillState.ACTIVE:
            raise Conflict(code="skill_proposal.skill_archived")
        await self._may_propose(actor, skill.space_id)
        description, content = base.description(description), base.content(content)
        if (description, content) == (skill.description, skill.content):
            raise ValidationFailed(code="skill_proposal.no_change")
        number = await SkillProposalFacts(self.session, actor.org_id).newest_number(skill.id)
        proposal = SkillProposal(
            kind=SkillProposalKind.CHANGE,
            space_id=skill.space_id,
            skill_id=skill.id,
            base_number=number,
            **_common(actor, description, content, reason, author, run_id),
        )
        return await self._made(actor, proposal)

    async def propose_new(
        self,
        actor: Actor,
        space_id: uuid.UUID | None,
        name: str,
        description: str,
        content: str,
        reason: str,
        *,
        author: Principal,
        run_id: uuid.UUID | None = None,
    ) -> SkillProposal:
        _check_author(actor, author)
        await base.gate(self.session, actor)
        if space_id is not None:
            await require(self.session, actor, Action.SPACE_READ, space_id)
        await self._may_propose(actor, space_id)
        name = base.name(name)
        description, content = base.description(description), base.content(content)
        skills = base.repo(self.session, actor)
        if await skills.name_taken(space_id, name):
            raise Conflict(code="skill.name_taken")
        proposal = SkillProposal(
            kind=SkillProposalKind.NEW,
            space_id=space_id,
            name=name,
            **_common(actor, description, content, reason, author, run_id),
        )
        return await self._made(actor, proposal)

    async def _may_propose(self, actor: Actor, space_id: uuid.UUID | None) -> None:
        if space_id is not None:
            await require(self.session, actor, Action.PAGE_EDIT, space_id)

    async def _made(self, actor: Actor, proposal: SkillProposal) -> SkillProposal:
        self.session.add(proposal)
        await self.session.flush()
        author = Principal(PrincipalType(proposal.author_type), proposal.author_id)
        acting = _Acting(actor.org_id, author)
        await skill_proposal_event(self.session, acting, SKILL_PROPOSAL_CREATED, proposal)
        return proposal

    # --- reading ---------------------------------------------------------------------

    async def list(
        self, actor: Actor, where: SkillProposalFilter, params: PageParams
    ) -> pagination.Page[SkillProposal]:
        """Newest first; a space filter for a space one cannot read: 404."""
        await base.gate(self.session, actor)
        if where.space_id is not None:
            await require(self.session, actor, Action.SPACE_READ, where.space_id)
        before = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await (await self.repo(actor)).page(where, before, params.limit + 1)
        return id_page(rows, params.limit, lambda p: p.id)

    async def get(
        self, actor: Actor, proposal_id: uuid.UUID, *, lock: bool = False
    ) -> SkillProposal:
        """404 `skill_proposal.not_found` unless the actor sees it (an admin's look into
        a team space is audited, as for its skills)."""
        proposal = await (await self.repo(actor)).get(proposal_id, lock=lock)
        if proposal is None:
            raise not_found()
        if proposal.space_id is not None:
            try:
                await require(self.session, actor, Action.SPACE_READ, proposal.space_id)
            except NotFound:
                raise not_found() from None
        return proposal

    async def skill_of(self, actor: Actor, proposal: SkillProposal) -> Skill | None:
        """The skill a proposal is about now (a change; an accepted new one)."""
        if proposal.skill_id is None:
            return None
        return await base.repo(self.session, actor).get(proposal.skill_id)

    async def shown(self, actor: Actor, proposals: Sequence[SkillProposal]) -> Shown:
        """Names (authors, deciders, changed skills) and accepted version numbers."""
        people = {Principal(PrincipalType(p.author_type), p.author_id) for p in proposals}
        people |= {Principal.user(p.decided_by_id) for p in proposals if p.decided_by_id}
        facts = SkillProposalFacts(self.session, actor.org_id)
        made = {p.result_version_id for p in proposals if p.result_version_id is not None}
        changed = {p.skill_id for p in proposals if p.skill_id is not None}
        return Shown(
            await base.repo(self.session, actor).names(people),
            await facts.skill_names(changed),
            await facts.version_numbers(made),
        )

    async def current_version(self, actor: Actor, skill_id: uuid.UUID) -> int:
        """The skill's `version` now (0 if the actor does not see it): what a release
        of a proposal for it is bound to."""
        skill = await base.repo(self.session, actor).get(skill_id)
        return skill.version if skill is not None else 0

    async def newest_number(self, actor: Actor, skill_id: uuid.UUID) -> int:
        return await SkillProposalFacts(self.session, actor.org_id).newest_number(skill_id)


@dataclass(frozen=True, slots=True)
class _Acting:
    org_id: uuid.UUID
    principal: Principal


def _check_author(actor: Actor, author: Principal) -> None:
    """An agent, or the acting person themselves."""
    if author.type == PrincipalType.AGENT:
        return
    if author != actor.principal or author.type != PrincipalType.USER:
        raise ValidationFailed(code="skill_proposal.bad_author")


def reason_text(value: str) -> str:
    text = value.strip()
    if not text or len(text) > MAX_REASON_CHARS:
        raise ValidationFailed(code="skill_proposal.invalid_reason")
    return text


def _common(
    actor: Actor,
    description: str,
    content: str,
    reason: str,
    author: Principal,
    run_id: uuid.UUID | None,
) -> dict[str, object]:
    return {
        "org_id": actor.org_id,
        "description": description,
        "content": content,
        "reason": reason_text(reason),
        "author_type": author.type,
        "author_id": author.id,
        "run_id": run_id,
        "state": SkillProposalState.OPEN,
    }
