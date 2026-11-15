"""Deciding approvals and answering questions (plan M6 decision 4, task 7).

Who sees one: whoever may see its run (`RunService.get`: the person who asked and the
agent's responsible person, each with `ai.use`, and `agent.manage`); everyone else
gets 404 (`approval.not_found`, `question.not_found`), as for an unknown id. The
call's arguments, a page's diff and a question's answer only the person it is
addressed to.

Who decides or answers: only that person (403 `approval.not_addressed`,
`question.not_addressed` for others who see it), and for an approval only while they
may do it themselves now: the tool's action (`ToolSpec.action`) in each object's
space, with their own rights (403 `approval.not_permitted`).

In one transaction, the run's row locked first and then the approval's (the same
order as the sweep that ends a run whose time ran out): 409 `approval.expired` past
its time or once expired, `approval.decided` when decided before (a second decision
loses), `approval.run_ended` when the run no longer waits for it (finished, or
someone asked it to stop), `approval.version_conflict` for another `version`. Then
the decision, and the run queued again (`control.resume_waiting`); the event
`approval.decided` (ids only) wakes a worker. The same for questions
(`question.*`).
"""

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor, can
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.models_base import utcnow
from app.core.outbox import emit
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.agents import control
from app.modules.agents.approvals.models import (
    Approval,
    ApprovalState,
    QuestionState,
    RunQuestion,
)
from app.modules.agents.approvals.repository import WaitedRepository
from app.modules.agents.control_repository import ControlRepository
from app.modules.agents.models import Run, RunState
from app.modules.agents.runs import RunService
from app.modules.agents.toolbox import external
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.proposals import rules
from app.modules.wiki import diffing
from app.modules.wiki.visibility import PageReader

PAGE_TOOLS = frozenset({"update_page", "propose_page_change"})  # a diff to show


@dataclass(frozen=True, slots=True)
class Shown[T]:
    """An approval or a question with its run, as the caller may see it."""

    row: T
    run: Run
    addressed: bool  # the caller is the person it asks


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, actor: Actor, approval_id: uuid.UUID) -> Shown[Approval]:
        return await _shown(self.session, actor, Approval, approval_id, "approval")

    async def mine(
        self, actor: Actor, state: ApprovalState | None, params: PageParams
    ) -> Page[Shown[Approval]]:
        """Those addressed to the caller, newest first."""
        before = decode_id_cursor(params.cursor) if params.cursor else None
        repo = WaitedRepository(self.session, actor.org_id)
        rows = await repo.approvals_of(actor.principal.id, state, before, params.limit + 1)
        page = id_page(rows, params.limit, lambda a: a.id)
        runs = await repo.runs({a.run_id for a in page.items})
        return Page[Shown[Approval]](
            items=[Shown(a, runs[a.run_id], True) for a in page.items],
            next_cursor=page.next_cursor,
        )

    async def diff(self, actor: Actor, approval_id: uuid.UUID) -> diffing.Diff | None:
        """The page's content now against the call's (None: too large to diff)."""
        shown = await self.get(actor, approval_id)
        approval = shown.row
        if not shown.addressed or approval.tool not in PAGE_TOOLS:
            raise NotFound(code="approval.not_found")
        page = await PageReader(self.session).readable(actor, uuid.UUID(approval.args["page_id"]))
        new = str(approval.args["content_md"])
        if not rules.fits(page.content_md, new):
            return None
        return await asyncio.to_thread(diffing.diff, page.title, page.content_md, page.title, new)

    async def decide(
        self,
        actor: Actor,
        approval_id: uuid.UUID,
        approve: bool,
        reason: str | None,
        version: int,
    ) -> Shown[Approval]:
        shown = await self.get(actor, approval_id)
        if not shown.addressed:
            raise Forbidden(code="approval.not_addressed")
        approval = shown.row
        spec = CATALOG.get(approval.tool)
        if spec is None and not external.is_external(approval.tool):
            raise Forbidden(code="approval.not_permitted")
        # An external tool's call changes nothing here: the person asked decides alone.
        action = await spec.needs(self.session, actor, approval.args) if spec else None
        if action is not None:
            for subject in approval.subjects:
                space_id = subject.get("space_id")
                if space_id and not await can(self.session, actor, action, uuid.UUID(space_id)):
                    raise Forbidden(code="approval.not_permitted")
        run = await _locked(self.session, actor, shown.run.id)
        repo = WaitedRepository(self.session, actor.org_id)
        locked = await repo.get(Approval, approval_id, lock=True)
        assert locked is not None
        if locked.state == ApprovalState.EXPIRED or locked.expires_at <= utcnow():
            raise Conflict(code="approval.expired")
        if locked.state != ApprovalState.PENDING:
            raise Conflict(code="approval.decided")
        await _waits(self.session, run, "approval")
        if locked.version != version:
            raise Conflict(
                code="approval.version_conflict", details={"current_version": locked.version}
            )
        locked.state = ApprovalState.APPROVED if approve else ApprovalState.REJECTED
        locked.decided_by = actor.principal.id
        locked.decided_at = utcnow()
        locked.reason = reason or None
        locked.version += 1
        await self.session.flush()
        await _resume(self.session, actor, run, "approval", locked)
        return Shown(locked, run, True)


class QuestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, actor: Actor, question_id: uuid.UUID) -> Shown[RunQuestion]:
        return await _shown(self.session, actor, RunQuestion, question_id, "question")

    async def answer(
        self, actor: Actor, question_id: uuid.UUID, text: str, version: int
    ) -> Shown[RunQuestion]:
        shown = await self.get(actor, question_id)
        if not shown.addressed:
            raise Forbidden(code="question.not_addressed")
        run = await _locked(self.session, actor, shown.run.id)
        repo = WaitedRepository(self.session, actor.org_id)
        locked = await repo.get(RunQuestion, question_id, lock=True)
        assert locked is not None
        if locked.state == QuestionState.EXPIRED or locked.expires_at <= utcnow():
            raise Conflict(code="question.expired")
        if locked.state != QuestionState.PENDING:
            raise Conflict(code="question.answered")
        await _waits(self.session, run, "question")
        if locked.version != version:
            raise Conflict(
                code="question.version_conflict", details={"current_version": locked.version}
            )
        locked.state = QuestionState.ANSWERED
        locked.answer = text
        locked.answered_at = utcnow()
        locked.version += 1
        await self.session.flush()
        await _resume(self.session, actor, run, "question", locked)
        return Shown(locked, run, True)


async def _shown[T: (Approval, RunQuestion)](
    session: AsyncSession, actor: Actor, model: type[T], id_: uuid.UUID, area: str
) -> Shown[T]:
    row = await WaitedRepository(session, actor.org_id).get(model, id_)
    if row is None:
        raise NotFound(code=f"{area}.not_found")
    try:
        run = await RunService(session).get(actor, row.run_id)
    except NotFound:
        raise NotFound(code=f"{area}.not_found") from None
    return Shown(row, run, row.addressed_to == actor.principal.id)


async def _locked(session: AsyncSession, actor: Actor, run_id: uuid.UUID) -> Run:
    run = await ControlRepository(session, actor.org_id).lock(run_id)
    assert run is not None  # seen a moment ago; a run is never deleted while it waits
    return run


async def _waits(session: AsyncSession, run: Run, area: str) -> None:
    """The run still waits for this: not finished, nobody asked it to stop."""
    stopped = await ControlRepository(session, run.org_id).cancelled_by(run.id)
    if run.state != RunState.WAITING or stopped is not None:
        raise Conflict(code=f"{area}.run_ended")


async def _resume(
    session: AsyncSession, actor: Actor, run: Run, area: str, row: Approval | RunQuestion
) -> None:
    await control.resume_waiting(session, actor.org_id, run.id)
    await emit(
        session,
        type=f"{area}.decided" if area == "approval" else f"{area}.answered",
        actor=actor,
        space_id=None,
        subject_type=area,
        subject_id=row.id,
        payload={
            f"{area}_id": str(row.id),
            "run_id": str(run.id),
            "conversation_id": str(run.conversation_id),
            "message_id": str(row.message_id) if row.message_id else None,
        },
    )
