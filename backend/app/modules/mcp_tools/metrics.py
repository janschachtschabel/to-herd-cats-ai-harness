"""The metric of `/mcp` (plan M8 decision 6): tool calls by tool (one of the
catalog's names) and outcome."""

from prometheus_client import Counter

from app.core.metrics import REGISTRY

MCP_CALLS = Counter(
    "herd_mcp_calls_total",
    "Tool calls through /mcp, by tool and outcome.",
    ["tool", "outcome"],
    registry=REGISTRY,
)
