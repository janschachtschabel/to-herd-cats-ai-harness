"""What a waiting run waits for (plan M6 decision 1 and 4, spec 8.2 and 8.3).

`approval`: a tool call of a run that needs a person's release (the agent's grant for
the tool is `confirm`). One per call (`run_id`, `step`, `call_id`). It keeps the call
(`tool`, `args`: the model's canonical arguments), what the call would change
(`subjects`: kind, id, version and space of each object) and `fingerprint`, a hash of
the tool, the arguments and those versions: the call runs after the release only if
the fingerprint is the same then (`approvals/gate.py`). `summary` is what the card
says (the tool and the ids it names; never content). It is addressed to one person
(`addressed_to`: who asked, or the agent's responsible person if that person is
inactive), who decides (`approved` or `rejected`, `decided_by`, `decided_at`, an
optional `reason` for the model) before `expires_at`, else it is `expired`; it is
`expired` too when its run ends otherwise (cancelled). `message_id`: the card in the
run's conversation. `outcome`: what became of an approved call, set in the transaction
where the run came back to it: `ran`, or `stale` (the fingerprint differed, so nothing
ran), or `failed` (the call's step timed out and was rolled back, recorded with the
timeout); null while it waits, when rejected or expired, and when the run stopped before
(its rights were gone). `personal`: asked because the run carries the personal mark
(module review M8 2, G2; `agents/personal_mark.py`).

`run_question`: `ask_user`'s question to the same person, `answer`ed (bounded) or
`expired` like an approval.

Both carry `version` (a decision or an answer names it: 409 otherwise).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, OrgScoped, UuidPk, utcnow

MAX_REASON_CHARS = 500
MAX_SUMMARY_CHARS = 500
MAX_QUESTION_CHARS = 1_000
MAX_ANSWER_CHARS = 4_000


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalOutcome(StrEnum):
    RAN = "ran"
    STALE = "stale"
    FAILED = "failed"  # the step ran into its bound and was rolled back: it did not run


class QuestionState(StrEnum):
    PENDING = "pending"
    ANSWERED = "answered"
    EXPIRED = "expired"


def _in(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class _Waited(UuidPk, OrgScoped):
    """What an approval and a question share: the call they belong to, whom they ask,
    until when, and the card."""

    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("run.id", ondelete="CASCADE"), nullable=False
    )
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    call_id: Mapped[str] = mapped_column(String(200), nullable=False)
    addressed_to: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("message.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Approval(_Waited, Base):
    __tablename__ = "approval"
    __table_args__ = (
        UniqueConstraint("run_id", "step", "call_id"),
        CheckConstraint(_in("state", ApprovalState), name="state"),
        CheckConstraint(
            "(state IN ('approved', 'rejected')) = (decided_at IS NOT NULL)"
            " AND (decided_at IS NULL) = (decided_by IS NULL)",
            name="decided",
        ),
        CheckConstraint(
            f"outcome IS NULL OR (state = 'approved' AND {_in('outcome', ApprovalOutcome)})",
            name="outcome",
        ),
        CheckConstraint(f"char_length(reason) <= {MAX_REASON_CHARS}", name="reason_length"),
        CheckConstraint(f"char_length(summary) <= {MAX_SUMMARY_CHARS}", name="summary_length"),
        Index("ix_approval_addressed_to_id", "addressed_to", "id"),
    )

    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    subjects: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(String(MAX_SUMMARY_CHARS), nullable=False)
    state: Mapped[ApprovalState] = mapped_column(String(16), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[ApprovalOutcome | None] = mapped_column(String(16))
    # Asked because the run carries the personal mark: every release then but a
    # message into its DM alone with her (module review M8 2, G2; M8 5, L2): what is
    # released can be read by others now or later, and is not marked afterwards.
    personal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )


class RunQuestion(_Waited, Base):
    __tablename__ = "run_question"
    __table_args__ = (
        UniqueConstraint("run_id", "step", "call_id"),
        CheckConstraint(_in("state", QuestionState), name="state"),
        CheckConstraint(
            "(state = 'answered') = (answer IS NOT NULL)"
            " AND (answer IS NULL) = (answered_at IS NULL)",
            name="answered",
        ),
        CheckConstraint(f"char_length(question) <= {MAX_QUESTION_CHARS}", name="question_length"),
        CheckConstraint(f"char_length(answer) <= {MAX_ANSWER_CHARS}", name="answer_length"),
        Index("ix_run_question_addressed_to_id", "addressed_to", "id"),
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[QuestionState] = mapped_column(String(16), nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
