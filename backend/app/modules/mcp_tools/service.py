"""One tool call through `/mcp` (plan M8 decisions 1, 3, 4 and 6).

The tool runs as it runs for an agent, through the same services, with the token's
actor: the person's rights held to the token's scope and to what the AI policy lets
the organisation's MCP data location receive (`tokens/resolve.py`). So nothing here
restates a permission rule; whatever the token may not see answers like an unknown
id, as the tool answers it.

A writing tool writes for the person with the token's name (`context.py`), only with
a `write` token (`exposed.py`) and only inside its write scope (its actor's). A tool's
refusal (not found, not allowed, changed meanwhile: `ToolResult.failed`) is a tool
error. Every call of a writing tool is audited (`mcp.write_call`: the token, the tool
and the outcome).

Each call runs in a savepoint of the request's transaction: a call that fails undoes
what it wrote, and the client gets a tool error without any internal detail. The
arguments are checked against the tool's model first; an invalid call names the
fields, never their values. A result longer than `MAX_TEXT_CHARS` is cut.

Every call is counted (`mcp_call`, the metric `herd_mcp_calls_total`) and logged with
the tool's name, the outcome and the time taken, never arguments or results.
"""

import logging
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.outbox import through_token
from app.modules.agents.actor import Reads
from app.modules.audit.recorder import record
from app.modules.mcp_tools.context import TokenContext
from app.modules.mcp_tools.exposed import Exposed, tool_for, tools_for
from app.modules.mcp_tools.metrics import MCP_CALLS
from app.modules.mcp_tools.models import McpCall, Outcome
from app.modules.mcp_tools.repository import McpCallRepository
from app.modules.tokens.resolve import TokenActor

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 100_000
CUT = "\n[cut: the result was longer than {limit} characters]"
FAILED = "The call failed. Try again later."
TARGET = "access_token"


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    is_error: bool
    outcome: Outcome


class UnknownTool(Exception):  # noqa: N818
    """The token is offered no tool of that name (a protocol error, not a tool's)."""


class McpToolService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def offered(self, token: TokenActor) -> tuple[Exposed, ...]:
        return tools_for(token)

    async def call(
        self, token: TokenActor, name: str, arguments: Mapping[str, Any] | None
    ) -> Answer:
        tool = tool_for(token, name)
        if tool is None:
            raise UnknownTool
        started = time.perf_counter()
        call_id = uuid7()
        answer = await self._answer(token, tool, arguments or {}, call_id)
        millis = round((time.perf_counter() - started) * 1000)
        await McpCallRepository(self.session, token.actor.org_id).add(
            McpCall(
                id=call_id,
                org_id=token.actor.org_id,
                token_id=token.token_id,
                tool=tool.name,
                outcome=answer.outcome,
                duration_ms=millis,
            )
        )
        if not tool.read_only:
            details = {"tool": tool.name, "outcome": answer.outcome.value}
            await record(
                self.session, token.actor, "mcp.write_call", TARGET, token.token_id, details
            )
        MCP_CALLS.labels(tool=tool.name, outcome=answer.outcome.value).inc()
        logger.info(
            "mcp.tool_call",
            extra={"tool": tool.name, "outcome": answer.outcome.value, "duration_ms": millis},
        )
        return answer

    async def _answer(
        self, token: TokenActor, tool: Exposed, arguments: Mapping[str, Any], call_id: uuid.UUID
    ) -> Answer:
        try:
            args = tool.spec.args.model_validate(dict(arguments))
        except ValidationError as exc:
            return Answer(_invalid(exc), True, Outcome.INVALID)
        ctx = TokenContext(
            self.session,
            token.actor,
            token.location,
            Reads(),
            token.token_id,
            token.name,
            call_id,
            token.agent.id if token.agent else None,
        )
        try:
            async with self.session.begin_nested():
                with through_token(token.token_id):  # its events name the token
                    result = await tool.run(ctx, args)
        except Exception as exc:
            logger.error("mcp.tool_failed", extra={"tool": tool.name, "error": type(exc).__name__})
            return Answer(FAILED, True, Outcome.FAILED)
        if result.failed:
            return Answer(_cut(result.text), True, Outcome.REFUSED)
        return Answer(_cut(result.text), False, Outcome.OK)


def _invalid(exc: ValidationError) -> str:
    fields = sorted({".".join(str(p) for p in e["loc"]) or "(arguments)" for e in exc.errors()})
    return "Invalid arguments: " + ", ".join(fields)


def _cut(text: str) -> str:
    if len(text) <= MAX_TEXT_CHARS:
        return text
    return text[:MAX_TEXT_CHARS] + CUT.format(limit=MAX_TEXT_CHARS)
