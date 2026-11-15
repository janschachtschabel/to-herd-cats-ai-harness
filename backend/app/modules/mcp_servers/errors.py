"""What calling an external tool can end in, besides a result (for task 7's runs to
turn into tool errors). Each has a fixed `code`; none carries the server's words, an
argument, a result or a credential."""

from app.mcp.client import RemoteStatus


class ExternalToolError(Exception):
    code = "mcp_tool.error"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ToolUnavailable(ExternalToolError):
    """Not callable: `reason` is `unknown` (no such server or tool in the
    organisation), `server_disabled`, `not_approved` (pending or blocked), `changed`
    (the server lists it differently from what was approved) or `missing` (the server
    no longer lists it)."""

    code = "mcp_tool.unavailable"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"external tool unavailable: {reason}")


class NotConnected(ExternalToolError):
    """The server acts with each person's own connector, and this person has none for
    it: they connect it under "my connections". Also: the OAuth connector the call
    needs has no tokens (never connected, disconnected, or its refresh token was
    refused); its owner connects it again."""

    code = "mcp_tool.not_connected"

    def __init__(self) -> None:
        super().__init__("no personal connector for this server")


class CredentialUnavailable(ExternalToolError):
    """The connector's secret cannot be resolved (unset variable, rotated key)."""

    code = "mcp_tool.credential_unavailable"

    def __init__(self) -> None:
        super().__init__("credential unavailable")


class RemoteFailed(ExternalToolError):
    """The server did not answer as it should; `status` says how (`RemoteStatus`)."""

    code = "mcp_tool.remote_failed"

    def __init__(self, status: RemoteStatus) -> None:
        self.status = status
        super().__init__(f"external tool call failed: {status}")
