"""The system as an MCP server (plan M8 decision 1): the SDK's low-level `Server`
offering tools only, served statelessly over Streamable HTTP.

Each request gets a server and a session manager of its own (`stateless`, JSON
answers): nothing is kept in the process between requests, no session id is handed
out, no stream stays open, and any API node can answer any request. The tools and
what they do come from `modules/mcp_tools` (the catalog's tools, with the token's
actor); this module only translates between the SDK's types and those.

The answer is collected and sent as one response (at most `MAX_RESPONSE_BYTES`), so
the request's database session commits before it goes out, as for any route.
"""

from dataclasses import dataclass, field
from typing import Any

import anyio
from mcp.server import Server, ServerRequestContext
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.shared.exceptions import MCPError
from mcp.types import (
    INVALID_PARAMS,
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
    ToolAnnotations,
)
from starlette.types import Message, Receive, Scope

from app.modules.mcp_tools.exposed import Exposed
from app.modules.mcp_tools.service import McpToolService, UnknownTool
from app.modules.tokens.resolve import TokenActor

NAME = "to-herd-cats-ai"
INSTRUCTIONS = (
    "The wiki and the tickets of to-herd-cats-ai, as far as your token may read them. "
    "Start with list_tree (the spaces) or search; read pages by id and tickets by key."
)
MAX_RESPONSE_BYTES = 1024 * 1024


class ResponseTooLarge(Exception):  # noqa: N818
    pass


@dataclass
class Reply:
    """The ASGI answer of the SDK, collected (status, headers, body up to a cap)."""

    limit: int
    status: int = 500
    headers: list[tuple[bytes, bytes]] = field(default_factory=list)
    body: bytearray = field(default_factory=bytearray)

    async def send(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.status = message["status"]
            self.headers = list(message.get("headers", []))
        elif message["type"] == "http.response.body":
            self.body.extend(message.get("body", b""))
            if len(self.body) > self.limit:
                raise ResponseTooLarge


async def serve(
    scope: Scope, body: bytes, service: McpToolService, token: TokenActor, max_request: int
) -> Reply:
    """Answer one MCP request (its body already read) for `token`."""
    manager = StreamableHTTPSessionManager(
        _server(service, token),
        json_response=True,
        stateless=True,
        max_request_body_size=max_request,
    )
    reply = Reply(MAX_RESPONSE_BYTES)
    try:
        async with manager.run():
            await manager.handle_request(scope, _replay(body), reply.send)
    except BaseExceptionGroup as group:
        if group.subgroup(ResponseTooLarge) is not None:
            raise ResponseTooLarge from None
        raise
    return reply


def _replay(body: bytes) -> Receive:
    """The request's body once, then nothing (a JSON answer does not listen for the
    client going away; whatever would, waits until the request is over)."""
    sent = False

    async def receive() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await anyio.sleep_forever()
        raise AssertionError("unreachable")

    return receive


def _server(service: McpToolService, token: TokenActor) -> Server[Any]:
    async def list_tools(
        ctx: ServerRequestContext[Any], params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        return ListToolsResult(tools=[_tool(tool) for tool in service.offered(token)])

    async def call_tool(
        ctx: ServerRequestContext[Any], params: CallToolRequestParams
    ) -> CallToolResult:
        try:
            answer = await service.call(token, params.name, params.arguments)
        except UnknownTool:
            raise MCPError(code=INVALID_PARAMS, message="Unknown tool") from None
        content = [TextContent(type="text", text=answer.text)]
        return CallToolResult(content=content, is_error=answer.is_error)

    return Server(NAME, instructions=INSTRUCTIONS, on_list_tools=list_tools, on_call_tool=call_tool)


def _tool(tool: Exposed) -> Tool:
    hints = ToolAnnotations(readOnlyHint=tool.read_only, destructiveHint=False)
    return Tool(
        name=tool.name,
        description=tool.spec.description,
        input_schema=tool.input_schema(),
        annotations=hints,
    )
