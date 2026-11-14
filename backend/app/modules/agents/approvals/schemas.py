"""The shapes of approvals and questions over HTTP (plan M6 task 7)."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.modules.agents.approvals.models import (
    MAX_ANSWER_CHARS,
    MAX_REASON_CHARS,
    Approval,
    ApprovalState,
    QuestionState,
    RunQuestion,
)
from app.modules.agents.approvals.service import PAGE_TOOLS, Shown


class ApprovalOut(BaseModel):
    """A tool call waiting for (or given) a person's release. `summary`: the tool and
    the ids the call names. `args`: the call's arguments, only for the person asked
    (null for others). `diff_url`: for a page's new content, where that person reads
    the diff against the page as it is now (`GET`), instead of the text."""

    id: uuid.UUID
    run_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID | None
    tool: str
    summary: str
    state: ApprovalState
    addressed_to: uuid.UUID
    args: dict[str, Any] | None
    diff_url: str | None
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    reason: str | None
    expires_at: datetime
    created_at: datetime
    version: int

    @classmethod
    def of(cls, shown: Shown[Approval]) -> "ApprovalOut":
        a = shown.row
        diff = f"/api/approvals/{a.id}/diff" if shown.addressed and a.tool in PAGE_TOOLS else None
        return cls(
            id=a.id,
            run_id=a.run_id,
            conversation_id=shown.run.conversation_id,
            message_id=a.message_id,
            tool=a.tool,
            summary=a.summary,
            state=a.state,
            addressed_to=a.addressed_to,
            args=a.args if shown.addressed else None,
            diff_url=diff,
            decided_by=a.decided_by,
            decided_at=a.decided_at,
            reason=a.reason,
            expires_at=a.expires_at,
            created_at=a.created_at,
            version=a.version,
        )


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
    """An agent's question; `answer` only for the person asked."""

    id: uuid.UUID
    run_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID | None
    question: str
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
            question=q.question,
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
