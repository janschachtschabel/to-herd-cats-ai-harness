"""A tool call that needs a person's release (plan M6 decision 4; spec 8.2).

A run offers a tool whose effective grant is `confirm` like any other. When the model
calls it, the host asks the gate first, in the call's transaction (`step_host.py`):

- No approval for the call yet: if the call changes nothing (`ToolSpec.subjects`
  gives None, such as `update_page`'s preview) it runs at once. Otherwise an approval
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
    run's rights are checked again for each object (`ToolSpec.action` where it is;
    the host checked the grant, the person and the agent before): if they are gone,
    the run ends `rights_revoked`. Then the tool runs, checking its rights itself.

The fingerprint: SHA-256 over the tool's name, the arguments as canonical JSON (keys
sorted) and each object's kind, id, version and space. Objects without a version
(a space, a conversation) count by their id and space.
"""

import hashlib
import json
from typing import Any

from pydantic import BaseModel

from app.core.access import can
from app.core.models_base import utcnow
from app.core.outbox import emit
from app.modules.agents.approvals import cards
from app.modules.agents.approvals.models import Approval, ApprovalOutcome, ApprovalState
from app.modules.agents.approvals.repository import WaitedRepository
from app.modules.agents.toolbox.base import Subject, ToolContext, ToolSpec, Wait
from app.modules.messaging.models import MessageKind
from app.runtime.loop import Halt, ToolResult

STALE = (
    "approval_stale: what this call would change has changed since the person released "
    "it, so it did not run. Read it again; call the tool again to ask for a new release."
)
REJECTED = "approval_rejected: the person did not release this call; it did not run."


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


async def gate(ctx: ToolContext, spec: ToolSpec, args: BaseModel) -> ToolResult | Wait | None:
    """None: the tool may run now; else what the call gets instead of running."""
    assert ctx.call is not None
    repo = WaitedRepository(ctx.session, ctx.run.org_id)
    found = await repo.for_call(Approval, ctx.run.id, ctx.call.step, ctx.call.id)
    subjects = await spec.subjects(ctx, args) if spec.subjects else []
    canonical = args.model_dump(mode="json")
    if found is None:
        if subjects is None:
            return None  # the call changes nothing (and finds what it may not, itself)
        return Wait((await _ask(ctx, spec, canonical, subjects)).expires_at)
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
    if spec.action is not None:
        for subject in subjects:
            if subject.space_id is not None and not await can(
                ctx.session, ctx.actor, spec.action, subject.space_id
            ):
                raise Halt("rights_revoked")
    await _settle(ctx, found, ApprovalOutcome.RAN)
    return None


async def _settle(ctx: ToolContext, approval: Approval, outcome: ApprovalOutcome) -> None:
    """Record what became of an approved call (rolled back with the call if the tool
    fails) and tell the card's readers."""
    approval.outcome = outcome
    await ctx.session.flush()
    await emit(
        ctx.session,
        type="approval.settled",
        actor=ctx.actor,
        space_id=None,
        subject_type="approval",
        subject_id=approval.id,
        payload={
            "approval_id": str(approval.id),
            "run_id": str(ctx.run.id),
            "conversation_id": str(ctx.run.conversation_id),
            "message_id": str(approval.message_id) if approval.message_id else None,
        },
    )


async def _ask(
    ctx: ToolContext, spec: ToolSpec, canonical: dict[str, Any], subjects: list[Subject]
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
            summary=cards.summary(spec.name, canonical),
            state=ApprovalState.PENDING,
            addressed_to=ctx.run.user_id,
            expires_at=cards.until(),
            created_at=utcnow(),
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
