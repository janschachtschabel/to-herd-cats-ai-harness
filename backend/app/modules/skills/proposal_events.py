"""The outbox events of skill proposals, written in the transaction of the change:
`skill_proposal.created`, `skill_proposal.accepted`, `skill_proposal.rejected`.

Subject: the proposal; space: its space (none for an organisation-wide one). Payload:
ids only, never a name, text or reason: `proposal_id`, and `author_id` when its
author is a person. The actor of a proposal made is its author (an agent's run: the
agent); of a decision, whoever decided. Handler: `notify_on_skill_proposal`
(`proposal_handlers.py`: activity entries and the live event `skill_proposal.changed`
for each person who should hear of it).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Acting, emit
from app.core.principal import PrincipalType
from app.modules.skills.proposal_models import SkillProposal

SKILL_PROPOSAL_CREATED = "skill_proposal.created"
SKILL_PROPOSAL_ACCEPTED = "skill_proposal.accepted"
SKILL_PROPOSAL_REJECTED = "skill_proposal.rejected"

SKILL_PROPOSAL_EVENTS = (SKILL_PROPOSAL_CREATED, SKILL_PROPOSAL_ACCEPTED, SKILL_PROPOSAL_REJECTED)


async def skill_proposal_event(
    session: AsyncSession, actor: Acting, type_: str, proposal: SkillProposal
) -> None:
    payload: dict[str, object] = {"proposal_id": str(proposal.id)}
    if proposal.author_type == PrincipalType.USER:
        payload["author_id"] = str(proposal.author_id)
    await emit(
        session,
        type=type_,
        actor=actor,
        space_id=proposal.space_id,
        subject_type="skill_proposal",
        subject_id=proposal.id,
        payload=payload,
    )
