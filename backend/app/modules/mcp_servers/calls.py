"""Calling an external tool (plan M8 decisions 7 and 9): what task 7's runs use.

`ToolCaller.call_tool(org_id, server_id, tool_name, arguments, on_behalf_of=user_id)`
returns an `UntrustedResult` or raises an `ExternalToolError` (`errors.py`):

1. `prepare` (reads only): the server is the organisation's and enabled, the tool is
   `approved`, still listed, and its stored fingerprint is the approved one; the
   credential is the shared connector or `on_behalf_of`'s own connector for this
   server (missing: `NotConnected`), resolved into headers here.
2. `execute` (no database): in one session with the server, the tools are listed and
   the tool is called only if the server lists it with exactly the approved
   fingerprint; the listing never approves anything. Through the egress guard, with a
   deadline and a cap on the answer. A 401 with an OAuth connector renews the token
   (in a transaction of its own) and calls once more.
3. A refusal in step 2 marks the tool `changed` (or missing) in the caller's
   transaction (`note_refusal`), then raises `ToolUnavailable`.

`call_tool` holds no lock while the server answers, but its transaction stays open; a
caller that must not hold one can run the three steps itself, committing between.
Arguments, results and credentials go into no log line, audit entry or error: the
log names ids, status, duration and size.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp import client as mcp
from app.mcp.client import CallResult, Endpoint, ListedTool, Refused, RemoteFailure, RemoteStatus
from app.modules.mcp_servers.endpoints import Renewal, prepared_endpoint
from app.modules.mcp_servers.errors import ExternalToolError, RemoteFailed, ToolUnavailable
from app.modules.mcp_servers.listing import apply, fingerprint
from app.modules.mcp_servers.models import ToolState
from app.modules.mcp_servers.repository import ServerRepository, ToolRepository

logger = logging.getLogger(__name__)

CALL_TIMEOUT_SECONDS = 60.0
MAX_RESULT_BYTES = 512 * 1024


@dataclass(frozen=True, slots=True)
class UntrustedResult:
    """A tool's answer. Untrusted data: the caller frames it (`runtime/untrusted.py`)
    and never takes it as an instruction, a grant or an approval."""

    is_error: bool
    text: str
    structured: Any
    size_bytes: int

    @property
    def untrusted(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class PreparedCall:
    org_id: uuid.UUID
    server_id: uuid.UUID
    tool_id: uuid.UUID
    tool_name: str
    approved_fingerprint: str
    endpoint: Endpoint
    # An OAuth connector's way to a renewed token after a 401 (`endpoints.py`).
    renewal: Renewal | None = field(default=None, repr=False)


class ToolCaller:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def call_tool(
        self,
        org_id: uuid.UUID,
        server_id: uuid.UUID,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        on_behalf_of: uuid.UUID,
    ) -> UntrustedResult:
        prepared = await self.prepare(org_id, server_id, tool_name, on_behalf_of=on_behalf_of)
        outcome = await execute(prepared, arguments)
        if isinstance(outcome, Refused):
            await self.note_refusal(prepared, outcome.listed)
            raise ToolUnavailable("missing" if outcome.listed is None else "changed")
        return outcome

    async def prepare(
        self, org_id: uuid.UUID, server_id: uuid.UUID, tool_name: str, *, on_behalf_of: uuid.UUID
    ) -> PreparedCall:
        server = await ServerRepository(self.session, org_id).get(server_id)
        tool = await ToolRepository(self.session, org_id).by_name(server_id, tool_name)
        if server is None or tool is None:
            raise ToolUnavailable("unknown")
        if not server.enabled:
            raise ToolUnavailable("server_disabled")
        if tool.missing:
            raise ToolUnavailable("missing")
        if tool.state == ToolState.CHANGED:
            raise ToolUnavailable("changed")
        approved = tool.approved_fingerprint
        if tool.state != ToolState.APPROVED or approved is None:
            raise ToolUnavailable("not_approved")
        if tool.fingerprint != approved:
            raise ToolUnavailable("changed")
        endpoint, renewal = await prepared_endpoint(self.session, server, on_behalf_of, strict=True)
        return PreparedCall(org_id, server.id, tool.id, tool.name, approved, endpoint, renewal)

    async def note_refusal(self, prepared: PreparedCall, listed: ListedTool | None) -> None:
        """The server listed the tool otherwise than approved (or not at all): store
        that, unless an admin decided on the tool meanwhile."""
        repo = ToolRepository(self.session, prepared.org_id)
        tool = await repo.by_name(prepared.server_id, prepared.tool_name, lock=True)
        if (
            tool is not None
            and tool.state == ToolState.APPROVED
            and tool.approved_fingerprint == prepared.approved_fingerprint
        ):
            apply(tool, listed)
            await self.session.flush()


async def execute(prepared: PreparedCall, arguments: dict[str, Any]) -> UntrustedResult | Refused:
    def accept(listed: ListedTool | None) -> bool:
        return listed is not None and fingerprint(listed) == prepared.approved_fingerprint

    async def call(endpoint: Endpoint) -> CallResult | Refused:
        return await mcp.call_tool(
            endpoint,
            prepared.tool_name,
            arguments,
            accept=accept,
            seconds=CALL_TIMEOUT_SECONDS,
            max_bytes=MAX_RESULT_BYTES,
        )

    started = time.monotonic()
    status, size = "ok", 0
    try:
        try:
            outcome = await call(prepared.endpoint)
        except RemoteFailure as failure:
            if failure.status != RemoteStatus.UNAUTHORIZED or prepared.renewal is None:
                raise
            outcome = await call(await prepared.renewal())  # once, with a renewed token
    except RemoteFailure as failure:
        status = failure.status.value
        raise RemoteFailed(failure.status) from None
    except ExternalToolError as error:  # the renewal's own failure
        status = error.code
        raise
    else:
        if isinstance(outcome, Refused):
            status = "refused"
            return outcome
        size = outcome.size_bytes
        status = "tool_error" if outcome.is_error else "ok"
        return UntrustedResult(outcome.is_error, outcome.text, outcome.structured, size)
    finally:
        logger.info(
            "mcp.tool_call",
            extra={
                "mcp_server_id": str(prepared.server_id),
                "mcp_tool_id": str(prepared.tool_id),
                "status": status,
                "size_bytes": size,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
