"""The shapes of approvals and questions over HTTP (plan M6 task 7)."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.modules.agents.approvals.models import (
    MAX_ANSWER_CHARS,
    MAX_REASON_CHARS,
    Approval,
    ApprovalOutcome,
    ApprovalState,
    QuestionState,
    RunQuestion,
)
from app.modules.agents.approvals.service import Shown
from app.modules.agents.approvals.shown import PAGE_TOOLS


class ApprovalExternalOut(BaseModel):
    """The external MCP server and tool an approval's call goes to (plan M8 decision
    8); their names are in `summary` ("<server> · <tool>")."""

    server_id: uuid.UUID
    tool_id: uuid.UUID


class ApprovalOut(BaseModel):
    """A tool call waiting for (or given) a person's release. `summary`: the tool and
    the ids the call names. `args`: the call's arguments, only for the person asked
    (null for others). `diff_url`: for a page's new content, where that person reads
    the diff against the page as it is now (`GET`), instead of the text. `step` and
    `call_id`: the call it waits for, as the run's journal names it (the step a run
    link points at). `outcome`: what became of the call once released: `ran`, or
    `stale` (what it would change had changed, so nothing ran); null before.
    `reason`: the person's reason for a rejection, and `args`, only for the person
    asked; for everyone else both are null and `redacted` is true (as in the run
    view, review M6 finding 6). `external`: for a call of an external tool (it sends
    `args` to that server once released), else null. `personal`: asked because the
    run carries the asker's personal mark and the call owes her release under it: what
    is released is written (or sent) where others can read it now or later (module
    review M8 2; M8 4, K5)."""

    id: uuid.UUID
    run_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID | None
    step: int
    call_id: str
    tool: str
    summary: str
    state: ApprovalState
    outcome: ApprovalOutcome | None
    addressed_to: uuid.UUID
    args: dict[str, Any] | None
    diff_url: str | None
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    reason: str | None
    redacted: bool
    external: ApprovalExternalOut | None
    expires_at: datetime
    created_at: datetime
    version: int
    personal: bool = False

    @classmethod
    def of(cls, shown: Shown[Approval]) -> "ApprovalOut":
        a = shown.row
        diff = f"/api/approvals/{a.id}/diff" if shown.addressed and a.tool in PAGE_TOOLS else None
        return cls(
            id=a.id,
            run_id=a.run_id,
            conversation_id=shown.run.conversation_id,
            message_id=a.message_id,
            step=a.step,
            call_id=a.call_id,
            tool=a.tool,
            summary=a.summary,
            state=a.state,
            outcome=a.outcome,
            addressed_to=a.addressed_to,
            args=a.args if shown.addressed else None,
            diff_url=diff,
            decided_by=a.decided_by,
            decided_at=a.decided_at,
            reason=a.reason if shown.addressed else None,
            redacted=not shown.addressed,
            external=_external(a.subjects),
            expires_at=a.expires_at,
            created_at=a.created_at,
            version=a.version,
            personal=a.personal,
        )


def _external(subjects: list[dict[str, Any]]) -> ApprovalExternalOut | None:
    ids = {s.get("kind"): s.get("id") for s in subjects}
    if "mcp_server" not in ids or "mcp_tool" not in ids:
        return None
    return ApprovalExternalOut(server_id=ids["mcp_server"], tool_id=ids["mcp_tool"])


class ApprovalDecide(BaseModel):
    """`approve` or `reject`; `reason` goes to the model (as untrusted text) on a
    rejection; `version`: the approval's, as read."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    reason: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_REASON_CHARS)] | None
    ) = None
    version: int


class QuestionOut(BaseModel):
    """An agent's question; `question` and `answer` only for the person asked (for
    everyone else null, with `redacted` true: the model's words, as in the run view)."""

    id: uuid.UUID
    run_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID | None
    question: str | None
    redacted: bool
    state: QuestionState
    addressed_to: uuid.UUID
    answer: str | None
    answered_at: datetime | None
    expires_at: datetime
    created_at: datetime
    version: int

    @classmethod
    def of(cls, shown: Shown[RunQuestion]) -> "QuestionOut":
        q = shown.row
        return cls(
            id=q.id,
            run_id=q.run_id,
            conversation_id=shown.run.conversation_id,
            message_id=q.message_id,
            question=q.question if shown.addressed else None,
            redacted=not shown.addressed,
            state=q.state,
            addressed_to=q.addressed_to,
            answer=q.answer if shown.addressed else None,
            answered_at=q.answered_at,
            expires_at=q.expires_at,
            created_at=q.created_at,
            version=q.version,
        )


class QuestionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_ANSWER_CHARS)
    ]
    version: int
