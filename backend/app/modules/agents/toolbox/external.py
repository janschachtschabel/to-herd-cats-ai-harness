"""External tools as a run offers them (plan M8 decisions 7 and 8): each approved tool
of the organisation's MCP servers as a `ToolSpec` beside the catalog's
(`catalog.py`); the host calls it (`agents/external_step.py`).

- **Name** for the model and for the agent's entry (`agent_tool`):
  `ext_<the tool's whole id, 32 hex>_<its name>` (`.` and anything else a model may
  not use becomes `_`; at most 64 characters, so the id is never cut). Stable for the
  tool, unique because its id is, never a name of the catalog (module review M8 1,
  finding 1: the first 12 hex of a UUIDv7 are only its millisecond). A run's journal
  of an earlier release may name a tool by its old name, `ext_<12 hex>_<name>`
  (`legacy_names`): the replay reads it as the tool's name now where it stands for
  exactly one tool of the organisation, else not at all.
- **Level and grant**: a `read` tool is level 2; a `write` tool is level 4 (acting
  outside) and never looser than `confirm`, so every call waits for the release of the
  person who asked, bound to a fingerprint over the tool, the arguments and the
  server's and the tool's versions (`subjects`): a tool or server that changed since
  makes the release stale. Both are offered only to an agent with an entry for them
  (`explicit`, `policy.py`), and only while usable (approved, listed exactly as
  approved, on an enabled server).
- **Description**: what it is and from which server; the server's own words follow
  framed as untrusted and cut to `MAX_DESCRIPTION_CHARS`, and so do its words about
  the arguments (`mcp_servers/schema_view.py`: descriptions, titles, allowed values,
  defaults, examples, cut). **Arguments**: only the structure of the tool's stored
  input schema (types, names, what is required, bounds; never a word of the server's);
  the server checks them. A tool whose schema cannot be offered so (too large, too
  deep, a name a model cannot take) is not usable (module review M8 1, finding 2).
- **Results** are untrusted data (`source="mcp"`, framed and cut by the loop); a
  failure is a result with a fixed code, never the server's words. Neither ever
  grants anything.
"""

import copy
import json
import re
import uuid
from collections.abc import Collection
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.toolbox.base import (
    Effect,
    Grant,
    RemoteTool,
    Subject,
    Subjects,
    ToolContext,
    ToolSpec,
)
from app.modules.mcp_servers import schema_view
from app.modules.mcp_servers.calls import UntrustedResult
from app.modules.mcp_servers.errors import (
    CredentialUnavailable,
    ExternalToolError,
    NotConnected,
    RemoteFailed,
    ToolUnavailable,
)
from app.modules.mcp_servers.models import Classification, McpServer, McpServerTool, ToolState
from app.modules.mcp_servers.repository import ServerRepository, ToolRepository
from app.runtime.loop import ToolResult, storable
from app.runtime.untrusted import frame_untrusted

PREFIX = "ext_"
MAX_NAME_CHARS = 64
MAX_DESCRIPTION_CHARS = 1_000
READ_LEVEL = 2
WRITE_LEVEL = 4
SOURCE = "mcp"
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")
_NAMED = re.compile(rf"^{PREFIX}([0-9a-f]{{32}})_")

OUTCOME_UNKNOWN = (
    "external_outcome_unknown: this call was sent to the external server, but its answer "
    "was never recorded (the work was interrupted). It was not sent again. Check in the "
    "external system whether it took effect before you call it again."
)
POLICY_REFUSED = (
    "policy_blocked: what this run has read may not be sent to this tool's server (the "
    "AI policy of a space read does not allow its data location). It was not called."
)
_UNAVAILABLE = (
    "external_tool_unavailable: this tool may not be called now (an admin must approve "
    "it again, or its server is switched off). It was not called."
)
_NOT_CONNECTED = (
    "external_tool_not_connected: the person you work for has not connected their own "
    "account for this server (under My connections). It was not called."
)
CALL_LIMIT = (
    "external_tool_limit: this run has sent {limit} calls to external tools, the most one "
    "run may. It was not called. Go on without it, or say what is left to do."
)
_CREDENTIAL = "external_tool_credential_unavailable: the server's access cannot be used now."
_FAILED = "external_tool_failed: the server did not answer as it should ({status})."
_TOOL_ERROR = "external_tool_error: the tool reported an error.\n"


class ExternalArgs(BaseModel):
    """Any JSON object; the model sees the tool's own schema (`schema_of`)."""

    model_config = ConfigDict(extra="allow")
    schema_of: ClassVar[dict[str, Any]] = {"type": "object"}

    @classmethod
    def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return copy.deepcopy(cls.schema_of)


def is_external(name: str) -> bool:
    return name.startswith(PREFIX)


def tool_name(tool: McpServerTool) -> str:
    return _named(tool.id.hex, tool.name)


def tool_id_of(name: str) -> uuid.UUID | None:
    """The tool a name of today stands for (None: no such name)."""
    found = _NAMED.match(name)
    return uuid.UUID(found.group(1)) if found else None


def legacy_name(remote: RemoteTool) -> str:
    """The name an earlier release gave the tool (not unique: see the module)."""
    return _named(remote.tool_id.hex[:12], remote.tool_name)


def legacy_names(specs: list[tuple[ToolSpec, bool]]) -> dict[str, str]:
    """Old name -> name now, for the old names that stand for exactly one tool."""
    found: dict[str, list[str]] = {}
    for spec, _ in specs:
        if spec.remote is not None:
            found.setdefault(legacy_name(spec.remote), []).append(spec.name)
    return {old: names[0] for old, names in found.items() if len(names) == 1}


def _named(key: str, name: str) -> str:
    return f"{PREFIX}{key}_{_UNSAFE.sub('_', name)}"[:MAX_NAME_CHARS]


def usable(tool: McpServerTool, server: McpServer) -> bool:
    return (
        server.enabled
        and tool.state == ToolState.APPROVED
        and tool.fingerprint == tool.approved_fingerprint
        and not tool.missing
        and tool.schema_problem is None
    )


async def offered_external(session: AsyncSession, org_id: uuid.UUID) -> list[ToolSpec]:
    """The organisation's usable external tools (the agent's entries pick from them)."""
    rows = await ToolRepository(session, org_id).of_org(usable_only=True)
    viewed = [(tool, server, schema_view.view(tool.input_schema)) for tool, server in rows]
    return [spec_of(t, s, v) for t, s, v in viewed if v.problem is None]


async def every_external(
    session: AsyncSession, org_id: uuid.UUID, approved_or: Collection[uuid.UUID] | None = None
) -> list[tuple[ToolSpec, bool]]:
    """Every external tool of the organisation, and whether it is usable now. With
    `approved_or`: only those holding an approval and those ids (an agent's grant
    list, bounded by `mcp_servers/tools.MAX_APPROVED_TOOLS`)."""
    rows = await ToolRepository(session, org_id).of_org(usable_only=False, approved_or=approved_or)
    found = []
    for tool, server in rows:
        seen = schema_view.view(tool.input_schema)
        found.append((spec_of(tool, server, seen), usable(tool, server) and not seen.problem))
    return found


def spec_of(tool: McpServerTool, server: McpServer, seen: schema_view.View) -> ToolSpec:
    writes = tool.classification == Classification.WRITE
    remote = RemoteTool(server.id, tool.id, server.name, tool.name, writes)
    return ToolSpec(
        tool_name(tool),
        _description(remote, tool.description, seen.words),
        _args_model(seen.structure),
        _host_only,
        WRITE_LEVEL if writes else READ_LEVEL,
        Effect.WRITE if writes else Effect.READ,
        _subjects_of(remote),
        floor=Grant.CONFIRM if writes else Grant.ALLOW,
        explicit=True,
        remote=remote,
    )


def result_of(remote: RemoteTool, outcome: UntrustedResult) -> ToolResult:
    text = outcome.text
    if not text.strip() and outcome.structured is not None:
        text = json.dumps(outcome.structured, ensure_ascii=False, default=str)
    if outcome.is_error:
        text = _TOOL_ERROR + text
    return ToolResult(SOURCE, storable(text), _attrs(remote))


def failure_of(remote: RemoteTool, error: ExternalToolError) -> ToolResult:
    """A call that could not be made or failed, as the model's result (fixed words)."""
    if isinstance(error, NotConnected):
        text = _NOT_CONNECTED
    elif isinstance(error, CredentialUnavailable):
        text = _CREDENTIAL
    elif isinstance(error, RemoteFailed):
        text = _FAILED.format(status=error.status.value)
    else:
        assert isinstance(error, ToolUnavailable)
        text = _UNAVAILABLE
    return ToolResult(SOURCE, text, _attrs(remote))


def refused(remote: RemoteTool) -> ToolResult:
    return ToolResult(SOURCE, POLICY_REFUSED, _attrs(remote))


def limited(remote: RemoteTool, limit: int) -> ToolResult:
    return ToolResult(SOURCE, CALL_LIMIT.format(limit=limit), _attrs(remote))


def unknown_outcome(remote: RemoteTool) -> ToolResult:
    return ToolResult(SOURCE, OUTCOME_UNKNOWN, _attrs(remote))


def summary(remote: RemoteTool) -> str:
    """What an approval's card says: the server and the tool, never an argument."""
    return f"{remote.server_name} · {remote.tool_name}"


def _attrs(remote: RemoteTool) -> dict[str, str]:
    return {"server": remote.server_name, "tool": remote.tool_name}


def _description(remote: RemoteTool, described: str, about_args: str) -> str:
    what = (
        "acts outside; every call waits for the release of the person you work for"
        if remote.writes
        else "reads"
    )
    server = remote.server_name
    words = described[:MAX_DESCRIPTION_CHARS]
    text = (
        f"External tool {remote.tool_name} of the server {server} ({what}). "
        "What you send it leaves this system. Its own description, from that server:\n"
        f"{frame_untrusted('mcp_tool_description', words, server=server)}"
    )
    if about_args:
        framed = frame_untrusted("mcp_tool_arguments", about_args, server=server)
        text += f"\nWhat that server says about the arguments:\n{framed}"
    return text


def _args_model(structure: dict[str, Any]) -> type[ExternalArgs]:
    shown = copy.deepcopy(structure)
    return type("ExternalToolArgs", (ExternalArgs,), {"schema_of": shown})


def _subjects_of(remote: RemoteTool) -> Subjects:
    async def subjects(ctx: ToolContext, args: Any) -> list[Subject] | None:
        org = ctx.run.org_id
        server = await ServerRepository(ctx.session, org).get(remote.server_id)
        tool = await ToolRepository(ctx.session, org).get(remote.server_id, remote.tool_id)
        return [
            Subject("mcp_server", remote.server_id, server.version if server else 0, None),
            Subject("mcp_tool", remote.tool_id, tool.version if tool else 0, None),
        ]

    return subjects


async def _host_only(ctx: ToolContext, args: Any) -> ToolResult:
    raise AssertionError("an external tool is called by the host (external_step.py)")
