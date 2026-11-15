"""Skill proposal routes (plan M6 task 9). Without `ai.use` or `skill.manage` the list
answers 404 `skill.not_found` (as every skill route); a proposal the caller does not
see answers 404 `skill_proposal.not_found`, as for an unknown id. Proposals are made
by agents' runs (`propose_skill`), so there is no route that makes one."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.skills.proposal_decisions import FinalText, SkillProposalDecisions
from app.modules.skills.proposal_models import SkillProposal, SkillProposalState
from app.modules.skills.proposal_repository import SkillProposalFilter
from app.modules.skills.proposal_schemas import (
    SkillProposalAccept,
    SkillProposalDetailOut,
    SkillProposalOut,
    SkillProposalReject,
)
from app.modules.skills.proposals import SkillProposalService

skill_proposals = APIRouter(prefix="/skill-proposals", tags=["skills"])


async def _detail(
    service: SkillProposalService, actor: ActorDep, proposal: SkillProposal
) -> SkillProposalDetailOut:
    skill = await service.skill_of(actor, proposal)
    number = await service.newest_number(actor, skill.id) if skill is not None else None
    shown = await service.shown(actor, [proposal])
    return SkillProposalDetailOut.detail(proposal, shown, skill, number)


@skill_proposals.get("", response_model=Page[SkillProposalOut])
async def list_skill_proposals(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    space_id: Annotated[uuid.UUID | None, Query(description="only this space's")] = None,
    org_wide: Annotated[
        bool | None, Query(description="true: only organisation-wide; false: only spaces'")
    ] = None,
    state: Annotated[SkillProposalState | None, Query(description="only this state")] = None,
) -> Page[SkillProposalOut]:
    """Newest first: those the caller may decide, and their own."""
    service = SkillProposalService(session)
    where = SkillProposalFilter(space_id=space_id, org_wide=org_wide, state=state)
    page = await service.list(actor, where, params)
    shown = await service.shown(actor, page.items)
    return Page[SkillProposalOut](
        items=[SkillProposalOut.of(p, shown) for p in page.items], next_cursor=page.next_cursor
    )


@skill_proposals.get("/{proposal_id}", response_model=SkillProposalDetailOut)
async def get_skill_proposal(
    proposal_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> SkillProposalDetailOut:
    service = SkillProposalService(session)
    return await _detail(service, actor, await service.get(actor, proposal_id))


@skill_proposals.post("/{proposal_id}/accept", response_model=SkillProposalDetailOut)
async def accept_skill_proposal(
    proposal_id: uuid.UUID, body: SkillProposalAccept, actor: ActorDep, session: SessionDep
) -> SkillProposalDetailOut:
    """403 unless the caller may manage skills in its scope; 409
    `skill_proposal.not_open`, `skill_proposal.version_conflict`,
    `skill_proposal.base_outdated` (the skill moved on: `details` holds its `version`
    and both texts; accept again with `skill_version`), `skill_proposal.skill_archived`,
    `skill.name_taken`."""
    final = FinalText(body.description, body.content, body.skill_version)
    decided = await SkillProposalDecisions(session).accept(actor, proposal_id, body.version, final)
    return await _detail(SkillProposalService(session), actor, decided)


@skill_proposals.post("/{proposal_id}/reject", response_model=SkillProposalDetailOut)
async def reject_skill_proposal(
    proposal_id: uuid.UUID, body: SkillProposalReject, actor: ActorDep, session: SessionDep
) -> SkillProposalDetailOut:
    decisions = SkillProposalDecisions(session)
    decided = await decisions.reject(actor, proposal_id, body.version, body.reason)
    return await _detail(SkillProposalService(session), actor, decided)
