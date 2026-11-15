"""An external tool's call in a run (plan M8 decisions 8 and 9; `step_host.py` hands
it here). No transaction is open while the remote server answers.

1. The step's first transaction, the run's row locked as in every step: the run is
   still this take-up's and not asked to stop, the tool still granted, the person and
   the agent still allowed together (`step_checks.py`). What the run has read may go
   to the server's data location (the strictest current policy of every space read,
   as before a model call); if not, the call is refused with `POLICY_REFUSED` as its
   result. The tool is still callable and its credential at hand
   (`ToolCaller.prepare`: the server's shared connector, or the asking person's own;
   the secret lives only in the endpoint's headers, never in the journal). A write
   tool passes the release of the asking person (`approvals/gate.py`: waiting,
   rejected and stale end the step as for any tool). A run that has sent
   `HERD_MCP_MAX_CALLS_PER_RUN` calls sends no more (`CALL_LIMIT` as the result).
   Then, before anything is sent, the call's `run_event` with `OUTCOME_UNKNOWN` as its
   result, committed.
2. The call (`calls.execute`): the server lists its tools again and the tool is
   called only as approved; through the egress guard, with a deadline and a cap.
3. A second transaction records the real result as a second `run_event` for the
   same call (the journal keeps the later one), or marks the tool `changed` or
   `missing` when the server listed it otherwise. A result through the asking
   person's own connector marks the run (`Reads.personal`, journaled with the result
   as `read.personal`): from then on it writes nothing others may read
   (`toolbox/writing.carries_draft`). A failure, the placeholder and a shared
   connector's result carry no mark.

A take-up after a lost worker replays the first entry: the model learns that the
outcome is unknown, and the call is never sent again on its own, read or write (a
write tool's release is used up: `ran`). A second transaction that runs out of time
leaves that same entry as the result. A call that fails before anything is sent
(unavailable, not connected, refused by the policy) records its failure as the
result in the first transaction.

Every call counts once in `herd_external_tool_calls_total` after its step committed
(`external_metrics.py`); a step that waits for a release counts when it runs again.
"""

import time
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.db_errors import is_timeout
from app.core.outbox import caused_by
from app.mcp.client import Refused
from app.modules.agents.approvals.gate import gate
from app.modules.agents.executor_repository import RunSteps
from app.modules.agents.external_metrics import CallOutcome, count, outcome_of
from app.modules.agents.external_repository import sent_calls
from app.modules.agents.run_models import STEP_STATEMENT_TIMEOUT_SECONDS, EventKind, Run
from app.modules.agents.step_checks import (
    granted,
    location_of,
    owned,
    policy_allows,
    run_actor_now,
)
from app.modules.agents.step_records import tool_content
from app.modules.agents.toolbox import external
from app.modules.agents.toolbox.base import CallRef, RunRef, ToolContext, ToolSpec, Wait
from app.modules.agents.toolbox.policy import Grant
from app.modules.agents.working import Unit, Working, once_more
from app.modules.ai.models import DataLocation
from app.modules.mcp_servers.calls import PreparedCall, ToolCaller, UntrustedResult, execute
from app.modules.mcp_servers.errors import ExternalToolError, ToolUnavailable
from app.modules.mcp_servers.models import ConnectorUse
from app.modules.mcp_servers.repository import ServerRepository
from app.runtime.loop import ToolCall, ToolResult

type Outcome = UntrustedResult | Refused | ExternalToolError


class Host(Protocol):
    """What of the run's host (`step_host.RunHost`) a call needs."""

    unit: Unit
    run: Working

    def seconds_left(self) -> float: ...
    def ref(self) -> RunRef: ...
    def next_seq(self) -> int: ...


@dataclass(frozen=True, slots=True)
class _Ended:
    """Nothing was sent: the result recorded in the first transaction, and why."""

    result: ToolResult
    outcome: CallOutcome


@dataclass(frozen=True, slots=True)
class _Sending:
    prepared: PreparedCall
    arguments: dict[str, Any]
    placeholder: ToolResult
    personal: bool  # through the asking person's own connector


async def call_external(
    host: Host, step: int, call: ToolCall, args: BaseModel, spec: ToolSpec
) -> ToolResult | Wait:
    writes = spec.remote is not None and spec.remote.writes
    first = await once_more(host.run, lambda: _before(host, step, call, args, spec))
    if isinstance(first, _Ended):
        count(first.outcome, writes=writes)
        return first.result
    if not isinstance(first, _Sending):
        return first  # waits for a release
    started = time.perf_counter()
    outcome: Outcome
    try:
        outcome = await execute(first.prepared, first.arguments)
    except ExternalToolError as error:
        outcome = error
    duration_ms = round((time.perf_counter() - started) * 1000)
    try:
        result = await once_more(
            host.run, lambda: _after(host, step, call, args, spec, first, outcome, duration_ms)
        )
    except Exception as exc:
        if is_timeout(exc):  # the call was sent: its first entry stands
            count(CallOutcome.UNKNOWN, writes=writes)
            return first.placeholder
        raise
    count(outcome_of(outcome), writes=writes)
    return result


async def _before(
    host: Host, step: int, call: ToolCall, args: BaseModel, spec: ToolSpec
) -> _Ended | Wait | _Sending:
    remote = spec.remote
    assert remote is not None
    async with host.unit() as session:
        statement = min(STEP_STATEMENT_TIMEOUT_SECONDS, host.seconds_left())
        steps, run, agent = await owned(session, host.run, statement)
        grant = await granted(session, host.run, agent, spec)
        actor = await run_actor_now(session, host.run, agent)
        claimed = host.run.claimed
        server = await ServerRepository(session, claimed.org_id).get(remote.server_id)
        refused = CallOutcome.REFUSED
        if server is not None and not await policy_allows(
            session, host.run, DataLocation(server.data_location)
        ):
            kept = await _record(host, steps, run, step, call, args, external.refused(remote))
            return _Ended(kept, refused)
        limit = get_settings().mcp_max_calls_per_run
        if await sent_calls(session, claimed.org_id, claimed.id) >= limit:
            capped = external.limited(remote, limit)
            return _Ended(
                await _record(host, steps, run, step, call, args, capped), CallOutcome.LIMITED
            )
        try:
            prepared = await ToolCaller(session).prepare(
                claimed.org_id, remote.server_id, remote.tool_name, on_behalf_of=claimed.user_id
            )
        except ExternalToolError as error:
            failed = external.failure_of(remote, error)
            kept = await _record(host, steps, run, step, call, args, failed)
            return _Ended(kept, outcome_of(error))
        location = await location_of(steps, host.run)
        ctx = ToolContext(
            session, actor, location, host.run.reads, host.ref(), CallRef(step, call.id)
        )
        held: ToolResult | Wait | None = None
        if grant == Grant.CONFIRM or remote.writes:  # a write tool: always (its floor)
            with caused_by(run.id):
                held = await gate(ctx, spec, args)
        if isinstance(held, Wait):
            await steps.wait(run, held.until)
            return held
        if held is not None:  # the release was rejected or is stale
            return _Ended(await _record(host, steps, run, step, call, args, held), refused)
        placeholder = external.unknown_outcome(remote)
        await _record(host, steps, run, step, call, args, placeholder)
        personal = server is not None and server.connector_scope == ConnectorUse.PERSONAL
        return _Sending(prepared, args.model_dump(mode="json"), placeholder, personal)


async def _after(
    host: Host,
    step: int,
    call: ToolCall,
    args: BaseModel,
    spec: ToolSpec,
    first: _Sending,
    outcome: Outcome,
    duration_ms: int,
) -> ToolResult:
    remote = spec.remote
    assert remote is not None
    async with host.unit() as session:
        steps, run, _ = await owned(session, host.run)
        if isinstance(outcome, Refused):
            await ToolCaller(session).note_refusal(first.prepared, outcome.listed)
            gone = ToolUnavailable("missing" if outcome.listed is None else "changed")
            result = external.failure_of(remote, gone)
        elif isinstance(outcome, ExternalToolError):
            result = external.failure_of(remote, outcome)
        else:
            result = external.result_of(remote, outcome)
        personal = first.personal and isinstance(outcome, UntrustedResult)
        if personal:  # the run's memory as recorded (a retry restores it)
            host.run.reads.personal = True
        return await _record(
            host, steps, run, step, call, args, result, duration_ms, personal=personal
        )


async def _record(
    host: Host,
    steps: RunSteps,
    run: Run,
    step: int,
    call: ToolCall,
    args: BaseModel,
    result: ToolResult,
    duration_ms: int = 0,
    *,
    personal: bool = False,
) -> ToolResult:
    content = tool_content(step, call, args, result, duration_ms, personal=personal)
    await steps.event(host.next_seq(), EventKind.TOOL_CALL, content)
    steps.keep(run)
    return result
