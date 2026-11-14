"""Approvals and questions of runs over HTTP (plan M6 task 7). One that the caller may
not see answers 404 (`approval.not_found`, `question.not_found`), as for an unknown
id; who sees, decides and answers what: `service.py`."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.agents.approvals.models import ApprovalState
from app.modules.agents.approvals.schemas import (
    ApprovalDecide,
    ApprovalOut,
    QuestionAnswer,
    QuestionOut,
)
from app.modules.agents.approvals.service import ApprovalService, QuestionService
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.wiki.version_schemas import HunkOut

approvals = APIRouter(prefix="/approvals", tags=["approvals"])
questions = APIRouter(prefix="/questions", tags=["approvals"])


@approvals.get("", response_model=Page[ApprovalOut])
async def my_approvals(
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
    state: Annotated[ApprovalState | None, Query(description="only this state")] = None,
) -> Page[ApprovalOut]:
    """Those addressed to the caller, newest first (`state=pending`: to decide)."""
    page = await ApprovalService(session).mine(actor, state, params)
    return Page[ApprovalOut](
        items=[ApprovalOut.of(s) for s in page.items], next_cursor=page.next_cursor
    )


@approvals.get("/{approval_id}", response_model=ApprovalOut)
async def get_approval(approval_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> ApprovalOut:
    return ApprovalOut.of(await ApprovalService(session).get(actor, approval_id))


@approvals.get("/{approval_id}/diff", response_model=list[HunkOut] | None)
async def approval_diff(
    approval_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> list[HunkOut] | None:
    """The page as it is now against the call's content, for the person asked (null:
    too large to compare)."""
    diff = await ApprovalService(session).diff(actor, approval_id)
    return None if diff is None else [HunkOut(kind=h.kind, lines=h.lines) for h in diff.hunks]


@approvals.post("/{approval_id}/decide", response_model=ApprovalOut)
async def decide_approval(
    approval_id: uuid.UUID, body: ApprovalDecide, actor: ActorDep, session: SessionDep
) -> ApprovalOut:
    shown = await ApprovalService(session).decide(
        actor, approval_id, body.decision == "approve", body.reason, body.version
    )
    return ApprovalOut.of(shown)


@questions.get("/{question_id}", response_model=QuestionOut)
async def get_question(question_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> QuestionOut:
    return QuestionOut.of(await QuestionService(session).get(actor, question_id))


@questions.post("/{question_id}/answer", response_model=QuestionOut)
async def answer_question(
    question_id: uuid.UUID, body: QuestionAnswer, actor: ActorDep, session: SessionDep
) -> QuestionOut:
    shown = await QuestionService(session).answer(actor, question_id, body.text, body.version)
    return QuestionOut.of(shown)
