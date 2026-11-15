"""A tool as a server lists it, held against what is stored: the fingerprint, which
names are taken in at all, and how a listing updates a stored tool."""

import hashlib
import json
import re
import uuid

from app.mcp.client import ListedTool
from app.modules.mcp_servers.models import (
    MAX_DESCRIPTION_CHARS,
    Classification,
    McpServerTool,
    ToolState,
)

# MCP tool names: 1 to 128 of A-Z, a-z, 0-9, `_`, `-`, `.` (others are skipped).
_NAME = re.compile(r"[A-Za-z0-9_.\-]{1,128}")


def usable(listed: ListedTool) -> bool:
    return _NAME.fullmatch(listed.name) is not None


def fingerprint(listed: ListedTool) -> str:
    """SHA-256 over name, full description and input schema (canonical JSON)."""
    material = json.dumps(
        {"name": listed.name, "description": listed.description, "schema": listed.input_schema},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode()).hexdigest()


def new_tool(org_id: uuid.UUID, server_id: uuid.UUID, listed: ListedTool) -> McpServerTool:
    """A tool seen for the first time: pending, proposed `read` only if annotated
    read-only by the server."""
    return McpServerTool(
        org_id=org_id,
        server_id=server_id,
        name=listed.name,
        description=listed.description[:MAX_DESCRIPTION_CHARS],
        input_schema=listed.input_schema,
        read_only_hint=listed.read_only,
        fingerprint=fingerprint(listed),
        classification=Classification.READ if listed.read_only else Classification.WRITE,
        state=ToolState.PENDING,
        missing=False,
    )


def apply(tool: McpServerTool, listed: ListedTool | None) -> bool:
    """Bring `tool` to what the server lists now (None: no longer listed). True when
    the tool's fingerprint changed. An approved tool whose fingerprint is no longer
    the approved one becomes `changed`; a changed one that is back to it, approved."""
    before = (tool.fingerprint, tool.state, tool.missing, tool.read_only_hint)
    if listed is None:
        tool.missing = True
    else:
        tool.missing = False
        tool.fingerprint = fingerprint(listed)
        tool.description = listed.description[:MAX_DESCRIPTION_CHARS]
        tool.input_schema = listed.input_schema
        tool.read_only_hint = listed.read_only
        matches = tool.fingerprint == tool.approved_fingerprint
        if tool.state == ToolState.APPROVED and not matches:
            tool.state = ToolState.CHANGED
        elif tool.state == ToolState.CHANGED and matches:
            tool.state = ToolState.APPROVED
    if (tool.fingerprint, tool.state, tool.missing, tool.read_only_hint) != before:
        tool.version += 1
    return tool.fingerprint != before[0]
