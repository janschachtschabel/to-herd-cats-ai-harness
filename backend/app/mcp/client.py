"""Talking to external MCP servers (plan M8 decision 7): Streamable HTTP only, through
the egress guard, never stdio. The only module that uses the SDK's client; services
call `list_tools` and `call_tool` and get plain data back.

- Every connection goes through `egress_x2.client` (the SDK's HTTP library is httpx2):
  https only, the name resolved and checked when connecting, no private (unless the
  operator lists the host, `Endpoint.rules`) or metadata addresses, the operator's
  proxy if one is set. The SDK follows a redirect only within
  the endpoint's origin; anything else fails (`redirect`).
- The whole operation has one deadline (`seconds`), each response body a size cap.
- The credential travels only in the headers of the endpoint, set on the HTTP client;
  it is in no error. What goes wrong becomes a `RemoteStatus`, never the server's
  words or an exception text (an SDK error may quote what the server answered).
- Each operation opens its own session and closes it: nothing is kept in the process.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent, Tool

from app.core import egress_x2
from app.core.egress import EgressBlocked, EgressRules

# Remote MCP servers: https and public addresses only (no `local` kind as for AI);
# private hosts only as the operator lists them (`Endpoint.rules`).
RULES = EgressRules(allow_private=False, allow_http=False)
MAX_PAGES = 20


class RemoteStatus(StrEnum):
    OK = "ok"
    BLOCKED = "blocked"  # the egress guard refused the address
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    UNAUTHORIZED = "unauthorized"  # 401
    FORBIDDEN = "forbidden"  # 403
    NOT_FOUND = "not_found"  # 404
    RATE_LIMITED = "rate_limited"  # 429
    REDIRECT = "redirect"  # 3xx to another origin: not followed
    SERVER_ERROR = "server_error"  # 5xx
    TOO_LARGE = "too_large"  # a response over the cap
    PROTOCOL_ERROR = "protocol_error"  # anything else the server got wrong
    SECRET_UNAVAILABLE = "secret_unavailable"  # noqa: S105 (a state: the connector's secret)


class RemoteFailure(Exception):  # noqa: N818
    def __init__(self, status: RemoteStatus) -> None:
        self.status = status
        super().__init__(f"MCP server call failed: {status}")


@dataclass(frozen=True, slots=True)
class Endpoint:
    url: str
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    proxy: str | None = field(default=None, repr=False)
    rules: EgressRules = RULES


@dataclass(frozen=True, slots=True)
class ListedTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool


@dataclass(frozen=True, slots=True)
class CallResult:
    is_error: bool
    text: str
    structured: Any
    size_bytes: int


@dataclass(frozen=True, slots=True)
class Refused:
    """The call was not made: `accept` refused the tool as the server lists it now
    (`listed` is None when the server no longer lists it)."""

    listed: ListedTool | None


async def list_tools(endpoint: Endpoint, *, seconds: float, max_bytes: int) -> list[ListedTool]:
    async def work(client: Client) -> list[ListedTool]:
        return await _all_tools(client)

    return await _run(endpoint, seconds, max_bytes, work)


async def call_tool(
    endpoint: Endpoint,
    name: str,
    arguments: dict[str, Any],
    *,
    accept: Callable[[ListedTool | None], bool],
    seconds: float,
    max_bytes: int,
) -> CallResult | Refused:
    """Lists the tools first, in the same session, and calls `name` only if `accept`
    takes it as listed now (the approval is checked against what the server says at
    the moment of the call, never approved by it)."""

    async def work(client: Client) -> CallResult | Refused:
        listed = next((t for t in await _all_tools(client) if t.name == name), None)
        if not accept(listed):
            return Refused(listed)
        return _result(await client.call_tool(name, arguments))

    return await _run(endpoint, seconds, max_bytes, work)


async def _run[T](
    endpoint: Endpoint, seconds: float, max_bytes: int, work: Callable[[Client], Awaitable[T]]
) -> T:
    statuses: list[int] = []

    async def note(response: httpx2.Response) -> None:
        statuses.append(response.status_code)

    http = egress_x2.client(
        endpoint.rules, timeout=seconds, proxy=endpoint.proxy, max_response_bytes=max_bytes
    )
    http.headers.update(endpoint.headers)
    http.event_hooks = {"response": [note]}
    transport = streamable_http_client(endpoint.url, http_client=http, max_sse_event_size=max_bytes)
    try:
        async with asyncio.timeout(seconds), http:
            async with Client(transport, cache=None) as client:
                return await work(client)
    except Exception as exc:  # the SDK wraps what its tasks raise in groups
        raise RemoteFailure(_status(exc, statuses)) from None


async def _all_tools(client: Client) -> list[ListedTool]:
    tools: list[ListedTool] = []
    cursor: str | None = None
    for _ in range(MAX_PAGES):
        page = await client.list_tools(cursor=cursor)
        tools.extend(_listed(t) for t in page.tools)
        if (cursor := page.next_cursor) is None:
            break
    return tools


def _listed(tool: Tool) -> ListedTool:
    read_only = tool.annotations is not None and tool.annotations.read_only_hint is True
    return ListedTool(tool.name, tool.description or "", dict(tool.input_schema), read_only)


def _result(result: CallToolResult) -> CallResult:
    parts = [
        block.text if isinstance(block, TextContent) else f"[{block.type} omitted]"
        for block in result.content
    ]
    text = "\n".join(parts)
    size = len(text.encode())
    if result.structured_content is not None:
        size += len(json.dumps(result.structured_content).encode())
    return CallResult(result.is_error, text, result.structured_content, size)


def _flatten(exc: BaseException) -> list[BaseException]:
    found: list[BaseException] = []
    pending: list[BaseException] = [exc]
    while pending and len(found) < 100:
        current = pending.pop()
        found.append(current)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(current.exceptions)
        for linked in (current.__cause__, current.__context__):
            if linked is not None and linked not in found:
                pending.append(linked)
    return found


_BY_STATUS = {
    401: RemoteStatus.UNAUTHORIZED,
    403: RemoteStatus.FORBIDDEN,
    404: RemoteStatus.NOT_FOUND,
    429: RemoteStatus.RATE_LIMITED,
}


def _status(exc: BaseException, statuses: list[int]) -> RemoteStatus:
    found = _flatten(exc)
    if any(isinstance(e, EgressBlocked) for e in found):
        return RemoteStatus.BLOCKED
    if any(isinstance(e, egress_x2.ResponseTooLarge) for e in found):
        return RemoteStatus.TOO_LARGE
    if any(isinstance(e, TimeoutError | httpx2.TimeoutException) for e in found):
        return RemoteStatus.TIMEOUT
    failed = [s for s in statuses if s >= 300]
    if failed:
        last = failed[-1]
        if last < 400:
            return RemoteStatus.REDIRECT
        if last >= 500:
            return RemoteStatus.SERVER_ERROR
        return _BY_STATUS.get(last, RemoteStatus.PROTOCOL_ERROR)
    if any(isinstance(e, httpx2.TransportError | OSError) for e in found):
        return RemoteStatus.UNREACHABLE
    return RemoteStatus.PROTOCOL_ERROR
