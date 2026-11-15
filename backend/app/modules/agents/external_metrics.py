"""The metric of external tool calls in runs (plan M8 task 13): every call counts once,
after its step committed, by outcome and by the tool's effect (`read`, `write`). Never
a server, a tool's name, an argument or a result as a label. External calls cost no
model tokens, so no budget counts them; `HERD_MCP_MAX_CALLS_PER_RUN` bounds them per
run (`limited`).

Outcomes: `ok`; `error` (the tool reported an error itself); `refused` (not sent for a
rule: the policy of what was read, a release rejected or stale, the tool unavailable,
changed or missing, the person not connected); `limited` (the run's cap); `failed`
(sent and failed, or the server's access could not be used: an OAuth renewal the
provider did not answer); `timeout`; `unknown` (sent, but its result could not be
recorded: the first journal entry stands)."""

from enum import StrEnum

from prometheus_client import Counter

from app.core.metrics import REGISTRY
from app.mcp.client import Refused, RemoteStatus
from app.modules.mcp_servers.calls import UntrustedResult
from app.modules.mcp_servers.errors import CredentialUnavailable, ExternalToolError, RemoteFailed


class CallOutcome(StrEnum):
    OK = "ok"
    ERROR = "error"
    REFUSED = "refused"
    LIMITED = "limited"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


_calls: Counter | None = None


def _counter() -> Counter:
    """Registered on first use (by a worker; an API process exports none)."""
    global _calls  # noqa: PLW0603 -- one registration per process
    if _calls is None:
        _calls = Counter(
            "herd_external_tool_calls_total",
            "Calls of agent runs to tools of external MCP servers, by outcome and by the "
            "tool's effect (read, write).",
            ["outcome", "effect"],
            registry=REGISTRY,
        )
    return _calls


def outcome_of(outcome: UntrustedResult | Refused | ExternalToolError) -> CallOutcome:
    if isinstance(outcome, UntrustedResult):
        return CallOutcome.ERROR if outcome.is_error else CallOutcome.OK
    if isinstance(outcome, RemoteFailed):
        timed_out = outcome.status == RemoteStatus.TIMEOUT
        return CallOutcome.TIMEOUT if timed_out else CallOutcome.FAILED
    if isinstance(outcome, CredentialUnavailable):
        return CallOutcome.FAILED
    return CallOutcome.REFUSED  # listed otherwise, unavailable, not connected


def count(outcome: CallOutcome, *, writes: bool) -> None:
    _counter().labels(outcome=outcome.value, effect="write" if writes else "read").inc()
