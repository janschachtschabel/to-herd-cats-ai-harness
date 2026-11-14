"""The outbox handler of skill proposals (plan M6 task 9), registered by name; the
worker imports this module (`app/worker/handlers.py`).

`notify_on_skill_proposal`, for each event:
- **Activity** (reason `skill_proposal`, bound to the proposal: a skill has no
  thread): on `skill_proposal.created` for those who may decide it, other than a
  person author; on `skill_proposal.accepted|rejected` for its author when that is a
  person other than whoever decided. Who may decide: for a space's proposal the
  space's moderators by membership (as for page proposals; system admins without a
  membership would hear of every space), for an organisation-wide one the owners
  and admins (`skill.manage`). Each only if they see the proposal now, by the rule
  of its routes (`sight.py`: `ai.use` or `skill.manage` included). Idempotent: a
  person gets one notification per proposal and reason.
- **Live**: one `skill_proposal.changed` (ids only) for each of those people and for
  a person author who sees it, on every event, so their lists reload.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.outbox import Event, emit
from app.core.principal import Principal, PrincipalType
from app.modules.groups.repository import GroupRepository
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.notification_repository import NotificationRepository
from app.modules.messaging.notifications import announce
from app.modules.proposals.repository import ProposalFacts
from app.modules.skills.proposal_events import SKILL_PROPOSAL_CREATED, SKILL_PROPOSAL_EVENTS
from app.modules.skills.proposal_models import SkillProposal
from app.modules.skills.proposal_repository import SkillProposalFacts, SkillProposalRepository
from app.modules.skills.sight import sight_of
from app.modules.users.repository import UserRepository
from app.worker.registry import handler

LIVE = "skill_proposal.changed"


async def notify_on_skill_proposal(session: AsyncSession, event: Event) -> None:
    if event.subject_type != "skill_proposal" or event.type not in SKILL_PROPOSAL_EVENTS:
        return
    proposal = await SkillProposalFacts(session, event.org_id).proposal(event.subject_id)
    if proposal is None:
        return
    person = proposal.author_id if proposal.author_type == PrincipalType.USER else None
    deciders = await _deciders(session, proposal)
    if event.type == SKILL_PROPOSAL_CREATED:
        wanted = deciders - {person}
    else:
        wanted = {person} if person is not None and person != event.actor.id else set()
    told = {u for u in deciders | {person} if u is not None}
    seeing = {u for u in told if await _sees(session, event.org_id, u, proposal.id)}
    rows = [(u, NotificationReason.SKILL_PROPOSAL) for u in sorted(wanted & seeing)]
    repo = NotificationRepository(session, event.org_id)
    for notification in await repo.add_for_skill_proposal(proposal.id, proposal.space_id, rows):
        await announce(session, event, notification)
    for user_id in sorted(seeing):
        await emit(
            session,
            type=LIVE,
            actor=event.acting,
            space_id=None,
            subject_type="skill_proposal",
            subject_id=proposal.id,
            payload={"user_id": str(user_id), "proposal_id": str(proposal.id)},
        )


async def _deciders(session: AsyncSession, proposal: SkillProposal) -> set[uuid.UUID]:
    if proposal.space_id is None:
        return set(await SkillProposalFacts(session, proposal.org_id).administrators())
    return set(await ProposalFacts(session, proposal.org_id).moderators(proposal.space_id))


async def _sees(
    session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, proposal_id: uuid.UUID
) -> bool:
    """Whether the person sees the proposal now, by the rule of its routes."""
    user = await UserRepository(session).get_current(org_id, user_id)
    if user is None or not user.is_active:
        return False
    principal = Principal.user(user.id)
    groups = await GroupRepository(session).group_ids_for(principal)
    actor = Actor(org_id, principal, user.system_role, groups)
    repo = SkillProposalRepository(session, await sight_of(session, actor))
    return await repo.get(proposal_id) is not None


handler(SKILL_PROPOSAL_EVENTS, "notify_on_skill_proposal")(notify_on_skill_proposal)
