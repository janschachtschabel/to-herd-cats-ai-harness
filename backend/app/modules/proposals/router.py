"""Page proposals over HTTP: the space's list, one proposal with its diff, accepting
and rejecting. No route makes a proposal (agents make them through the service, plan
M6 decision 8). A proposal one may not see answers 404 `proposal.not_found`, as for
an unknown id."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.proposals.decisions import ProposalDecisions
from app.modules.proposals.models import ProposalState
from app.modules.proposals.schemas import (
    ProposalAcceptIn,
    ProposalDetailOut,
    ProposalMergeOut,
    ProposalOut,
    ProposalRejectIn,
)
from app.modules.proposals.service import ProposalService
from app.modules.wiki.version_schemas import HunkOut

space_proposals = APIRouter(prefix="/spaces/{space_id}/proposals", tags=["proposals"])
proposals = APIRouter(prefix="/proposals", tags=["proposals"])


@space_proposals.get("", response_model=Page[ProposalOut])
async def list_proposals(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    state: Annotated[ProposalState | None, Query(description="only this state")] = None,
) -> Page[ProposalOut]:
    """Newest first: those of the space the caller may see (page editors, and an
    author their own)."""
    service = ProposalService(session)
    page = await service.list(actor, space_id, state, params)
    names = await service.names(actor, page.items)
    return Page[ProposalOut](
        items=[ProposalOut.of(p, names) for p in page.items], next_cursor=page.next_cursor
    )


@proposals.get("/{proposal_id}", response_model=ProposalDetailOut)
async def get_proposal(
    proposal_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> ProposalDetailOut:
    service = ProposalService(session)
    detail = await service.detail(actor, proposal_id)
    names = await service.names(actor, [detail.proposal])
    diff = detail.diff
    return ProposalDetailOut(
        **ProposalOut.of(detail.proposal, names).model_dump(),
        content_md=detail.proposal.content_md,
        diff=[HunkOut(kind=h.kind, lines=h.lines) for h in diff.hunks] if diff else None,
        too_large=diff is None,
        page_version=detail.page_version,
        current_content_md=detail.current_content_md,
        merge=ProposalMergeOut.of(detail.merged) if detail.merged else None,
    )


@proposals.post("/{proposal_id}/accept", response_model=ProposalOut)
async def accept_proposal(
    proposal_id: uuid.UUID, body: ProposalAcceptIn, actor: ActorDep, session: SessionDep
) -> ProposalOut:
    """409 `proposal.base_outdated` when the page moved on (see the merge in the
    error's `details`); accept again with `merged_content` and `page_version`."""
    proposal = await ProposalDecisions(session).accept(
        actor,
        proposal_id,
        body.version,
        merged_content=body.merged_content,
        page_version=body.page_version,
    )
    return ProposalOut.of(proposal, await ProposalService(session).names(actor, [proposal]))


@proposals.post("/{proposal_id}/reject", response_model=ProposalOut)
async def reject_proposal(
    proposal_id: uuid.UUID, body: ProposalRejectIn, actor: ActorDep, session: SessionDep
) -> ProposalOut:
    proposal = await ProposalDecisions(session).reject(
        actor, proposal_id, body.version, body.reason
    )
    return ProposalOut.of(proposal, await ProposalService(session).names(actor, [proposal]))
