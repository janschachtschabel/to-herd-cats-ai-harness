"""A tool call that needs a person's release (plan M6 decision 4; spec 8.2).

A run offers a tool whose effective grant is `confirm` like any other. When the model
calls it, the host asks the gate first, in the call's transaction (`step_host.py`):

- No approval for the call yet: if the call changes nothing (`ToolSpec.subjects`
  gives None, such as `update_page`'s preview) it runs at once (`Passed.UNCHANGED`:
  never as a released call; under the personal mark it runs `previewing`, module
  review M8 3, H1). Otherwise an approval
  is made (the canonical arguments, what the call would change and the fingerprint),
  its card is posted (`cards.py`) and the run waits (`Wait`, until the approval
  expires: `HERD_AI_APPROVAL_HOURS`, 72 by default).
- The run is taken up again (a decision resumes it) and the call comes again with
  the same step and call id:
  - still pending: it waits on (or, past its time, ends `approval_expired`);
  - `expired`: the run ends `approval_expired`;
  - `rejected`: the tool does not run; its result is `approval_rejected` with the
    person's reason (framed as untrusted like every result);
  - `approved`: the fingerprint is computed anew from the objects as they are now.
    If it differs (an object changed or is gone), the tool does not run and its
    result is `approval_stale`: the model may call it again and so ask anew. Then the
    run's rights are checked again for each object (`ToolSpec.needs` where it names
    an action;
    the host checked the grant, the person and the agent before): if they are gone,
    the run ends `rights_revoked`. Then the tool runs, checking its rights itself
    (`outcome = ran`, with its effect; a step that times out is rolled back and
    recorded `failed`, `settle_timed_out`).

The fingerprint: SHA-256 over the tool's name, the arguments as canonical JSON (keys
sorted) and each object's kind, id, version and space. Objects without a version
(a space, a conversation) count by their id and space. An external tool's call
(plan M8 decision 8) names its server and its tool with their versions: a server or
a tool that changed since the release makes it stale; its card names the server and
the tool, never an argument (`toolbox/external.py`).

Under the personal mark (`agents/personal_mark.py`) every write but into the run's
DM alone with the person asks the same way, whatever the tool's grant
(`personal_step.py`); such an approval is `personal`, and so is a `confirm` grant's
only when the call owes that release (module review M8 4, K5). A personal card says
that what is released can be read by others now or later, and shows it in full; a
call whose content cannot be shown in full is refused instead (`shown.py`).
"""

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import can
from app.core.models_base import utcnow
from app.core.outbox import Acting, EventActor, emit
from app.core.principal import Principal
from app.modules.agents.approvals import cards
from app.modules.agents.approvals.models import Approval, ApprovalOutcome, ApprovalState
from app.modules.agents.approvals.repository import WaitedRepository
from app.modules.agents.approvals.shown import NOT_SHOWN, shown_in_full
from app.modules.agents.toolbox import external
from app.modules.agents.toolbox.base import CallRef, RunRef, Subject, ToolContext, ToolSpec, Wait
from app.modules.messaging.models import MessageKind
from app.runtime.loop import Halt, ToolResult

STALE = (
    "approval_stale: what this call would change has changed since the person released "
    "it, so it did not run. Read it again; call the tool again to ask for a new release."
)
REJECTED = "approval_rejected: the person did not release this call; it did not run."


class Passed(StrEnum):
    """Why the gate lets a call run now."""

    RELEASED = "released"  # the person released exactly this call
    UNCHANGED = "unchanged"  # the call changes nothing (a preview): nobody released it


def fingerprint(tool: str, args: dict[str, Any], subjects: list[Subject]) -> str:
    canonical = json.dumps(
        {
            "tool": tool,
            "args": args,
            "subjects": [_subject(s) for s in subjects],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def gate(
    ctx: ToolContext, spec: ToolSpec, args: BaseModel, *, personal: bool = False
) -> ToolResult | Wait | Passed:
    """`Passed`: the tool may run now (and why); else what the call gets instead of
    running. `personal`: asked because the run carries the personal mark (its card
    says so)."""
    assert ctx.call is not None
    repo = WaitedRepository(ctx.session, ctx.run.org_id)
    found = await repo.for_call(Approval, ctx.run.id, ctx.call.step, ctx.call.id)
    subjects = await spec.subjects(ctx, args) if spec.subjects else []
    canonical = args.model_dump(mode="json")
    if found is None:
        if subjects is None:
            return Passed.UNCHANGED  # (and finds what it may not, itself)
        if personal and not await shown_in_full(
            ctx.session, ctx.actor, spec.name, canonical, for_ai=True
        ):  # she releases only what she sees in full (module review M8 3, H5)
            return ToolResult("approval", NOT_SHOWN, {"tool": spec.name}, failed=True)
        return Wait((await _ask(ctx, spec, canonical, subjects, personal)).expires_at)
    if found.state == ApprovalState.PENDING:
        if found.expires_at <= utcnow():
            raise Halt("approval_expired")
        return Wait(found.expires_at)
    if found.state == ApprovalState.EXPIRED:
        raise Halt("approval_expired")
    if found.state == ApprovalState.REJECTED:
        said = f" The person's reason: {found.reason}" if found.reason else ""
        return ToolResult("approval", REJECTED + said, {"tool": spec.name})
    if subjects is None or fingerprint(spec.name, canonical, subjects) != found.fingerprint:
        await _settle(ctx, found, ApprovalOutcome.STALE)
        return ToolResult("approval", STALE, {"tool": spec.name})
    if (action := await spec.needs(ctx.session, ctx.actor, canonical)) is not None:
        for subject in subjects:
            if subject.space_id is not None and not await can(
                ctx.session, ctx.actor, action, subject.space_id
            ):
                raise Halt("rights_revoked")
    await _settle(ctx, found, ApprovalOutcome.RAN)
    return Passed.RELEASED


async def _settle(ctx: ToolContext, approval: Approval, outcome: ApprovalOutcome) -> None:
    """Record what became of an approved call (rolled back with the call if the tool
    fails) and tell the card's readers."""
    await settle(ctx.session, ctx.actor, ctx.run, approval, outcome)


async def settle_timed_out(session: AsyncSession, run: RunRef, call: CallRef) -> None:
    """A released call whose step timed out (rolled back, `outcome` with it): `failed`,
    in the transaction that records the timeout as the call's result (module review
    M6 2, finding 7). Nothing for a call without a release."""
    repo = WaitedRepository(session, run.org_id)
    found = await repo.for_call(Approval, run.id, call.step, call.id)
    if found is None or found.state != ApprovalState.APPROVED or found.outcome is not None:
        return
    by = EventActor(run.org_id, Principal.agent(run.agent_id))
    await settle(session, by, run, found, ApprovalOutcome.FAILED)


async def settle(
    session: AsyncSession,
    by: Acting,
    run: RunRef,
    approval: Approval,
    outcome: ApprovalOutcome,
) -> None:
    approval.outcome = outcome
    await session.flush()
    await emit(
        session,
        type="approval.settled",
        actor=by,
        space_id=None,
        subject_type="approval",
        subject_id=approval.id,
        payload={
            "approval_id": str(approval.id),
            "run_id": str(run.id),
            "conversation_id": str(run.conversation_id),
            "message_id": str(approval.message_id) if approval.message_id else None,
        },
    )


async def _ask(
    ctx: ToolContext,
    spec: ToolSpec,
    canonical: dict[str, Any],
    subjects: list[Subject],
    personal: bool,
) -> Approval:
    assert ctx.call is not None
    approval = await WaitedRepository(ctx.session, ctx.run.org_id).add(
        Approval(
            org_id=ctx.run.org_id,
            run_id=ctx.run.id,
            step=ctx.call.step,
            call_id=ctx.call.id,
            tool=spec.name,
            args=canonical,
            subjects=[_subject(s) for s in subjects],
            fingerprint=fingerprint(spec.name, canonical, subjects),
            summary=external.summary(spec.remote)
            if spec.remote
            else cards.summary(spec.name, canonical),
            state=ApprovalState.PENDING,
            addressed_to=ctx.run.user_id,
            expires_at=cards.until(),
            created_at=utcnow(),
            personal=personal,
        )
    )
    card = await cards.post(
        ctx, MessageKind.APPROVAL, approval.id, approval.summary, approval.addressed_to
    )
    approval.message_id = card.id
    await ctx.session.flush()
    return approval


def _subject(subject: Subject) -> dict[str, Any]:
    return {
        "kind": subject.kind,
        "id": str(subject.id),
        "version": subject.version,
        "space_id": str(subject.space_id) if subject.space_id else None,
    }
