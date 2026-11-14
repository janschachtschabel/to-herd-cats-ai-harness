"""Skill proposal schemas (plan M6 task 9). Lengths of a final text are checked by the
service with the skill's error codes; a reason is at most 300 characters."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from app.core.principal import Principal, PrincipalType
from app.modules.skills.models import Skill
from app.modules.skills.proposal_models import (
    MAX_REASON_CHARS,
    SkillProposal,
    SkillProposalKind,
    SkillProposalState,
)
from app.modules.skills.schemas import SkillAuthorOut


@dataclass(frozen=True, slots=True)
class Shown:
    """What a proposal's output names besides the row: people and agents, skill
    names, the numbers of the versions accepted proposals made."""

    names: dict[Principal, str]
    skills: dict[uuid.UUID, str]
    numbers: dict[uuid.UUID, int]


class SkillProposalOut(BaseModel):
    """`name`: a new skill's name, or the changed skill's name now. `base_number`: the
    skill's newest version when it was proposed (a change). `result_number`: the
    version an accepted proposal made (none if the skill already held its text)."""

    id: uuid.UUID
    kind: SkillProposalKind
    space_id: uuid.UUID | None
    skill_id: uuid.UUID | None
    name: str | None
    reason: str
    author: SkillAuthorOut
    run_id: uuid.UUID | None
    state: SkillProposalState
    base_number: int | None
    decided_by: SkillAuthorOut | None
    decided_at: datetime | None
    decision_reason: str | None
    result_number: int | None
    version: int
    created_at: datetime

    @classmethod
    def of(cls, p: SkillProposal, shown: Shown) -> Self:
        decided = None
        if p.decided_by_id is not None:
            decided = SkillAuthorOut.of(PrincipalType.USER, p.decided_by_id, shown.names)
        name = p.name if p.kind == SkillProposalKind.NEW else None
        if name is None and p.skill_id is not None:
            name = shown.skills.get(p.skill_id)
        result = shown.numbers.get(p.result_version_id) if p.result_version_id else None
        return cls(
            id=p.id,
            kind=p.kind,
            space_id=p.space_id,
            skill_id=p.skill_id,
            name=name,
            reason=p.reason,
            author=SkillAuthorOut.of(p.author_type, p.author_id, shown.names),
            run_id=p.run_id,
            state=p.state,
            base_number=p.base_number,
            decided_by=decided,
            decided_at=p.decided_at,
            decision_reason=p.decision_reason,
            result_number=result,
            version=p.version,
            created_at=p.created_at,
        )


class SkillTextOut(BaseModel):
    description: str
    content: str


class SkillNowOut(SkillTextOut):
    """The changed skill as it is now: `version` is what accepting a moved-on
    proposal sends as `skill_version`; `number` its newest version."""

    version: int
    number: int


class SkillProposalDetailOut(SkillProposalOut):
    """With the proposed text and, for a change, the skill now (`outdated`: it has a
    newer version than `base_number`; accepting then needs `skill_version`)."""

    proposed: SkillTextOut
    current: SkillNowOut | None
    outdated: bool

    @classmethod
    def detail(
        cls, p: SkillProposal, shown: Shown, skill: Skill | None, number: int | None
    ) -> Self:
        base = SkillProposalOut.of(p, shown).model_dump()
        current = None
        if p.kind == SkillProposalKind.CHANGE and skill is not None and number is not None:
            current = SkillNowOut(
                description=skill.description,
                content=skill.content,
                version=skill.version,
                number=number,
            )
        outdated = current is not None and current.number != p.base_number
        proposed = SkillTextOut(description=p.description, content=p.content)
        return cls(**base, proposed=proposed, current=current, outdated=outdated)


class SkillProposalAccept(BaseModel):
    """`description`/`content`: the final text (none: as proposed). `skill_version`:
    the skill's `version` the moderator decided on; needed once the skill moved on
    (409 `skill_proposal.base_outdated` names it)."""

    model_config = ConfigDict(extra="forbid")

    version: int
    description: str | None = None
    content: str | None = None
    skill_version: int | None = None


class SkillProposalReject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    reason: str | None = Field(default=None, max_length=MAX_REASON_CHARS)
