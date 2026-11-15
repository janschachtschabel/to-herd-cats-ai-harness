import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.principal import PrincipalType
from app.modules.proposals.merge import Merge
from app.modules.proposals.models import MAX_REASON_CHARS, PageProposal, ProposalKind, ProposalState
from app.modules.proposals.service import Names
from app.modules.wiki.models import MAX_CONTENT_CHARS
from app.modules.wiki.version_schemas import HunkOut

Reason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_REASON_CHARS)
]


class ProposalAuthorOut(BaseModel):
    """A person or an agent, by name (null if it is gone)."""

    type: PrincipalType
    id: uuid.UUID
    name: str | None


class ProposalDeciderOut(BaseModel):
    id: uuid.UUID
    name: str | None


class ProposalOut(BaseModel):
    """A proposal without its content. `kind`: `change` of `page_id`, based on its
    version `base_version`; or `new`, a page `title` under `parent_id` (null: the top
    level), whose `page_id` is the page it became once accepted. `ai`: made by an agent
    (`run_id`: its run) or by a person's AI client through an access token
    (`via_token`: the token's name, plan M8). `decided_by`/`decided_at`: who
    accepted, rejected or (its author's person) withdrew it, and when;
    `decision_reason`: a rejection's reason; `result_version`: the page version an
    acceptance wrote (null if the page held that content already). `version`: name
    it when deciding (stale → 409)."""

    id: uuid.UUID
    space_id: uuid.UUID
    kind: ProposalKind
    state: ProposalState
    page_id: uuid.UUID | None
    parent_id: uuid.UUID | None
    title: str | None
    base_version: int | None
    reason: str
    author: ProposalAuthorOut
    ai: bool
    run_id: uuid.UUID | None
    via_token: str | None = None
    decided_by: ProposalDeciderOut | None
    decided_at: datetime | None
    decision_reason: str | None
    result_version: int | None
    version: int
    created_at: datetime

    @classmethod
    def of(cls, proposal: PageProposal, names: Names) -> "ProposalOut":
        p = proposal
        decided_by = None
        if p.decided_by_id is not None:
            decided_by = ProposalDeciderOut(
                id=p.decided_by_id, name=names.people.get(p.decided_by_id)
            )
        author_names = names.agents if p.author_type == PrincipalType.AGENT else names.people
        return cls(
            id=p.id,
            space_id=p.space_id,
            kind=p.kind,
            state=p.state,
            page_id=p.page_id,
            parent_id=p.parent_id,
            title=p.title,
            base_version=p.base_version,
            reason=p.reason,
            author=ProposalAuthorOut(
                type=p.author_type, id=p.author_id, name=author_names.get(p.author_id)
            ),
            ai=p.author_type == PrincipalType.AGENT or p.via_token is not None,
            run_id=p.run_id,
            via_token=p.via_token,
            decided_by=decided_by,
            decided_at=p.decided_at,
            decision_reason=p.decision_reason,
            result_version=names.versions.get(p.result_version_id) if p.result_version_id else None,
            version=p.version,
            created_at=p.created_at,
        )


class ProposalSegmentOut(BaseModel):
    """`clean`: merged `lines`; `conflict`: the stretch as in the base, as proposed and
    as on the page now (the other three lists are empty for the other kind)."""

    kind: Literal["clean", "conflict"]
    lines: list[str]
    base: list[str]
    proposed: list[str]
    current: list[str]


class ProposalMergeOut(BaseModel):
    """The three-way merge of base, proposal and the page now: `merged_content` when it
    merges cleanly (null with conflicts), and the merge in `segments`."""

    clean: bool
    merged_content: str | None
    segments: list[ProposalSegmentOut]

    @classmethod
    def of(cls, merged: Merge) -> "ProposalMergeOut":
        return cls(
            clean=merged.clean,
            merged_content=merged.text,
            segments=[
                ProposalSegmentOut(
                    kind=s.kind, lines=s.lines, base=s.base, proposed=s.proposed, current=s.current
                )
                for s in merged.segments
            ],
        )


class ProposalDetailOut(ProposalOut):
    """With the proposed `content_md` and `diff`, line by line from the base (empty for
    a new page) to it; null when the texts are beyond `HERD_DIFF_MAX_LINES`
    (`too_large`). For an open change: `page_version`, the page's version now (name it
    with `merged_content` when accepting); and when the page's content is no longer
    the base, `current_content_md` and `merge` (null when too large)."""

    content_md: str
    diff: list[HunkOut] | None
    too_large: bool
    page_version: int | None
    current_content_md: str | None
    merge: ProposalMergeOut | None


class ProposalAcceptIn(BaseModel):
    """`version`: the proposal's. `merged_content` with `page_version` (the page's
    version it was merged against): the text to write instead of the proposal, after
    a 409 `proposal.base_outdated`."""

    model_config = ConfigDict(extra="forbid")

    version: int
    merged_content: str | None = Field(default=None, max_length=MAX_CONTENT_CHARS)
    page_version: int | None = None

    @model_validator(mode="after")
    def _merged_needs_the_page_version(self) -> "ProposalAcceptIn":
        if self.merged_content is not None and self.page_version is None:
            raise ValueError("merged_content needs page_version")
        return self


class ProposalRejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    reason: Reason | None = None
