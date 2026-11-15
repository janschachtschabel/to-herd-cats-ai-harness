"""The outbox events of proposals, written in the transaction of the change:
`proposal.created`, `proposal.accepted`, `proposal.rejected`, `proposal.withdrawn`.

Subject: the proposal; space: its space. Payload: ids only, never a title, content
or reason: `proposal_id`, and `page_id`, the page whose thread gets the entry (a
change: its page; a new page: its parent, none at the top level); `author_id` when its
author is a person (who always gets its live events, plan M6 task 6). The actor of a
proposal made or withdrawn is its author (an agent's run: the agent); of a decision,
whoever decided. Handlers:
`proposal_timeline` and `notify_on_proposal` (`handlers.py`), and `publish_live`,
which makes each one `proposal.changed` for the space's page editors.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Acting, emit
from app.core.principal import PrincipalType
from app.modules.proposals.models import PageProposal, ProposalKind

PROPOSAL_CREATED = "proposal.created"
PROPOSAL_ACCEPTED = "proposal.accepted"
PROPOSAL_REJECTED = "proposal.rejected"
PROPOSAL_WITHDRAWN = "proposal.withdrawn"

PROPOSAL_EVENTS = (PROPOSAL_CREATED, PROPOSAL_ACCEPTED, PROPOSAL_REJECTED, PROPOSAL_WITHDRAWN)


def thread_page_id(proposal: PageProposal) -> uuid.UUID | None:
    """The page whose thread tells of the proposal."""
    return proposal.page_id if proposal.kind == ProposalKind.CHANGE else proposal.parent_id


async def proposal_event(
    session: AsyncSession, actor: Acting, type_: str, proposal: PageProposal
) -> None:
    page_id = thread_page_id(proposal)
    payload: dict[str, object] = {
        "proposal_id": str(proposal.id),
        "page_id": str(page_id) if page_id else None,
    }
    if proposal.author_type == PrincipalType.USER:
        payload["author_id"] = str(proposal.author_id)
    await emit(
        session,
        type=type_,
        actor=actor,
        space_id=proposal.space_id,
        subject_type="proposal",
        subject_id=proposal.id,
        payload=payload,
    )
