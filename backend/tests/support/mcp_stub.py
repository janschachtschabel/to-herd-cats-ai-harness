"""A local MCP server for tests (plan M8: never the real network): a real Streamable
HTTP server built with the SDK's low-level `Server`, stateless, one JSON answer per
request.

Scriptable through `state` (shared with the test): the tool list (`tools`, dicts with
`name`, `description`, `input_schema` and optionally `read_only`), what a call answers
(`results` by tool name: `{"text": ...}`, `{"structured": ...}`, `{"is_error": True}`
or `{"huge": n}` for a text of n bytes; without one it says which tool was called),
`delay` (seconds before every answer), `redirect_to` (every MCP request answers 302
there), `failures` (status codes for the next requests) and `require_header` (a
`(name, value)` pair; without it a request answers 401). Every request is logged with
its headers (`log`), so a test asserts what a credential put on the wire without our
code ever logging it.

In tests: the `mcp_stub` fixture (`tests/factories_mcp.py`) runs it with TLS for the
name `mcp.test` in a thread; `url` is its endpoint. As a process (e2e):
`python -m tests.support.mcp_stub --port 8098` (plain http, endpoint `/mcp`) with
control routes under `/_stub` (`GET /_stub/log`, `POST /_stub/reset`,
`POST /_stub/script` with any of `tools`, `results`, `delay`, `redirect_to`,
`failures`, `require_header`).
"""

import argparse
import asyncio
import socket
import tempfile
import threading
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server import Server, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
    ToolAnnotations,
)
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from tests.support.openai_stub import self_signed

TLS_NAME = "mcp.test"


def default_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "search_issues",
            "description": "Search issues by text.",
            "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
            "read_only": True,
        },
        {
            "name": "create_issue",
            "description": "Create an issue.",
            "input_schema": {"type": "object", "properties": {"title": {"type": "string"}}},
        },
    ]


@dataclass
class LoggedRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: str


@dataclass
class McpStubState:
    log: list[LoggedRequest] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=default_tools)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    failures: deque[int] = field(default_factory=deque)
    delay: float = 0.0
    redirect_to: str | None = None
    require_header: tuple[str, str] | None = None

    def reset(self) -> None:
        self.log.clear()
        self.tools = default_tools()
        self.results.clear()
        self.calls.clear()
        self.failures.clear()
        self.delay = 0.0
        self.redirect_to = None
        self.require_header = None

    def texts(self) -> str:
        """Everything the stub received, as one string to search."""
        return "\n".join(f"{r.path} {r.headers} {r.body}" for r in self.log)


def _tool(spec: dict[str, Any]) -> Tool:
    annotations = ToolAnnotations(read_only_hint=True) if spec.get("read_only") else None
    return Tool(
        name=spec["name"],
        description=spec.get("description"),
        input_schema=spec.get("input_schema", {"type": "object"}),
        annotations=annotations,
    )


def build_server(state: McpStubState) -> Server[Any]:
    async def list_tools(
        ctx: ServerRequestContext[Any], params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        return ListToolsResult(tools=[_tool(t) for t in state.tools])

    async def call_tool(
        ctx: ServerRequestContext[Any], params: CallToolRequestParams
    ) -> CallToolResult:
        arguments = dict(params.arguments or {})
        state.calls.append((params.name, arguments))
        script = state.results.get(params.name, {})
        if "huge" in script:
            return CallToolResult(content=[TextContent(text="x" * int(script["huge"]))])
        text = script.get("text", f"called {params.name}")
        return CallToolResult(
            content=[TextContent(text=text)],
            structured_content=script.get("structured"),
            is_error=bool(script.get("is_error", False)),
        )

    return Server("mcp-stub", on_list_tools=list_tools, on_call_tool=call_tool)


class _Gate:
    """Logs every request, then delays, fails, redirects or refuses as scripted."""

    def __init__(self, app: ASGIApp, state: McpStubState) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        body = await request.body()
        state = self.state
        state.log.append(
            LoggedRequest(request.method, request.url.path, dict(request.headers), body.decode())
        )
        if state.delay:
            await asyncio.sleep(state.delay)
        answer: Response | None = None
        if state.failures:
            answer = JSONResponse({"error": "scripted"}, status_code=state.failures.popleft())
        elif state.redirect_to:
            answer = RedirectResponse(state.redirect_to, status_code=307)
        elif state.require_header is not None:
            name, value = state.require_header
            if request.headers.get(name) != value:
                answer = JSONResponse({"error": "unauthorized"}, status_code=401)
        if answer is not None:
            await answer(scope, receive, send)
            return
        sent = False

        async def replay() -> dict[str, Any]:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def build_app(state: McpStubState) -> Starlette:
    server = build_server(state)
    mcp_app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        assert server._session_manager is not None
        async with server._session_manager.run():
            yield

    async def control_log(request: Request) -> Response:
        return JSONResponse([r.__dict__ for r in state.log])

    async def control_reset(request: Request) -> Response:
        state.reset()
        return JSONResponse({})

    async def control_script(request: Request) -> Response:
        script = await request.json()
        state.failures.extend(script.get("failures", []))
        for name in ("tools", "results", "delay", "redirect_to"):
            if name in script:
                setattr(state, name, script[name])
        if "require_header" in script:
            state.require_header = tuple(script["require_header"] or ()) or None  # type: ignore[assignment]
        return JSONResponse({})

    routes = [
        Route("/_stub/log", control_log, methods=["GET"]),
        Route("/_stub/reset", control_reset, methods=["POST"]),
        Route("/_stub/script", control_script, methods=["POST"]),
        Mount("/", app=_Gate(mcp_app, state)),
    ]
    return Starlette(routes=routes, lifespan=lifespan)


class McpStub:
    """The stub on 127.0.0.1 in a thread of its own, serving https for `TLS_NAME`
    (tests resolve it to 127.0.0.1 through `egress.Network`)."""

    def __init__(self) -> None:
        self.state = McpStubState()
        self._dir = tempfile.TemporaryDirectory()
        self.cert_path, key_path = self_signed(Path(self._dir.name), [TLS_NAME])
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self.port: int = self._socket.getsockname()[1]
        config = uvicorn.Config(
            build_app(self.state),
            log_config=None,
            log_level=None,
            access_log=False,
            ssl_certfile=str(self.cert_path),
            ssl_keyfile=str(key_path),
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run, kwargs={"sockets": [self._socket]}, daemon=True
        )

    @property
    def url(self) -> str:
        return f"https://{TLS_NAME}:{self.port}/mcp"

    def start(self) -> "McpStub":
        self._thread.start()
        for _ in range(500):
            if self._server.started:
                return self
            threading.Event().wait(0.01)
        raise RuntimeError("stub did not start")

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
        self._socket.close()
        self._dir.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8098)
    args = parser.parse_args()
    uvicorn.run(build_app(McpStubState()), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
