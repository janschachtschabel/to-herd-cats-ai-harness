"""Deciding skill proposals (plan M6 task 9; the rules: `proposals.py`)."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import Conflict, Forbidden
from app.core.models_base import utcnow
from app.core.principal import Principal, PrincipalType
from app.modules.skills import base
from app.modules.skills.models import Skill, SkillState
from app.modules.skills.proposal_events import (
    SKILL_PROPOSAL_ACCEPTED,
    SKILL_PROPOSAL_REJECTED,
    skill_proposal_event,
)
from app.modules.skills.proposal_models import (
    SkillProposal,
    SkillProposalKind,
    SkillProposalState,
)
from app.modules.skills.proposals import SkillProposalService, reason_text
from app.modules.skills.service import SkillChange, SkillDraft, SkillService


@dataclass(frozen=True, slots=True)
class FinalText:
    """What the moderator accepts instead of the proposal's text (None: as proposed)."""

    description: str | None = None
    content: str | None = None
    skill_version: int | None = None  # the skill's `version` the moderator saw


class SkillProposalDecisions:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.proposals = SkillProposalService(session)

    async def accept(
        self, actor: Actor, proposal_id: uuid.UUID, version: int, final: FinalText
    ) -> SkillProposal:
        proposal = await self._decidable(actor, proposal_id, version)
        description = final.description or proposal.description
        content = final.content or proposal.content
        own = (description, content) == (proposal.description, proposal.content)
        who = Principal(PrincipalType(proposal.author_type), proposal.author_id)
        who = who if own else actor.principal
        skills = SkillService(self.session)
        before = 0
        if proposal.kind == SkillProposalKind.NEW:
            assert proposal.name is not None
            draft = SkillDraft(proposal.name, description, content, proposal.space_id)
            skill = await skills.create(actor, draft, author=who)
        else:
            assert proposal.skill_id is not None
            skill = await base.visible(self.session, actor, proposal.skill_id, lock=True)
            before = await self._current(actor, proposal, skill, final)
            change = SkillChange(skill.version, description=description, content=content)
            skill = await skills.update(actor, skill.id, change, author=who)
        after = await self.proposals.newest_number(actor, skill.id)
        made = None
        if after > before:  # no new version when the skill already held the text
            made = await base.repo(self.session, actor).version(skill.id, after)
        await self._decide(actor, proposal, SkillProposalState.ACCEPTED)
        proposal.skill_id = skill.id
        proposal.result_version_id = made.id if made is not None else None
        await self.session.flush()
        await skill_proposal_event(self.session, actor, SKILL_PROPOSAL_ACCEPTED, proposal)
        return proposal

    async def _current(
        self, actor: Actor, proposal: SkillProposal, skill: Skill, final: FinalText
    ) -> int:
        """The skill's newest version number; 409 unless the skill is as the proposal
        (or the moderator) saw it."""
        if skill.state != SkillState.ACTIVE:
            raise Conflict(code="skill_proposal.skill_archived")
        newest = await self.proposals.newest_number(actor, skill.id)
        moved = newest != proposal.base_number
        seen = final.skill_version
        if (seen is not None and seen != skill.version) or (moved and seen is None):
            raise Conflict(
                code="skill_proposal.base_outdated",
                details={
                    "skill_version": skill.version,
                    "current": {"description": skill.description, "content": skill.content},
                    "proposed": {
                        "description": proposal.description,
                        "content": proposal.content,
                    },
                },
            )
        return newest

    async def reject(
        self, actor: Actor, proposal_id: uuid.UUID, version: int, reason: str | None
    ) -> SkillProposal:
        proposal = await self._decidable(actor, proposal_id, version)
        text = reason_text(reason) if reason is not None and reason.strip() else None
        await self._decide(actor, proposal, SkillProposalState.REJECTED, text)
        await self.session.flush()
        await skill_proposal_event(self.session, actor, SKILL_PROPOSAL_REJECTED, proposal)
        return proposal

    async def _decidable(self, actor: Actor, proposal_id: uuid.UUID, version: int) -> SkillProposal:
        proposal = await self.proposals.get(actor, proposal_id, lock=True)
        if actor.read_scope is not None or not await base.may_manage(
            self.session, actor, proposal.space_id
        ):
            raise Forbidden(code="auth.permission_denied")
        if proposal.state != SkillProposalState.OPEN:
            raise Conflict(code="skill_proposal.not_open", details={"state": proposal.state})
        if proposal.version != version:
            raise Conflict(
                code="skill_proposal.version_conflict",
                details={"current_version": proposal.version},
            )
        return proposal

    async def _decide(
        self,
        actor: Actor,
        proposal: SkillProposal,
        state: SkillProposalState,
        reason: str | None = None,
    ) -> None:
        proposal.state = state
        proposal.decided_by_id = actor.principal.id
        proposal.decided_at = utcnow()
        proposal.decision_reason = reason
        proposal.version += 1
