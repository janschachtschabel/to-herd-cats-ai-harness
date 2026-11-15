"""Which tools of the catalog `/mcp` offers (plan M8 decisions 1 and 3): not a second
list, the catalog's own tools (`agents/toolbox/catalog.py`), with their names,
descriptions and argument models.

Only tools that work without a run are offered: their runner takes a `CallContext`
(no run, no conversation, no agent), so mypy keeps them from reaching for one; each
entry names the catalog's runner itself (`tests/test_mcp_offered_tools.py` checks
that it is the same function). Tools that wait for a person (`ask_user`), that end a run
(`submit_result`) or that belong to an agent (memory, skills, past runs, the run's
conversation) are not offered at all, and neither is any tool that needs a person's
release in the system (`confirm`, decision 3).
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.agents.toolbox import listing, reading
from app.modules.agents.toolbox.base import CallContext, Effect, ToolSpec
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.tokens.models import TokenMode
from app.runtime.loop import ToolResult

Runner = Callable[[CallContext, Any], Awaitable[ToolResult]]


@dataclass(frozen=True, slots=True)
class Exposed:
    spec: ToolSpec
    run: Runner

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def read_only(self) -> bool:
        return self.spec.effect == Effect.READ

    def input_schema(self) -> dict[str, Any]:
        return self.spec.args.model_json_schema()


def _exposed(name: str, run: Runner) -> Exposed:
    return Exposed(CATALOG[name], run)


READ_TOOLS: tuple[Exposed, ...] = (
    _exposed("search", reading.search),
    _exposed("read_page", reading.read_page),
    _exposed("read_ticket", reading.read_ticket),
    _exposed("list_tree", listing.list_tree),
    _exposed("list_versions", listing.list_versions),
    _exposed("search_tickets", listing.search_tickets),
)

_BY_MODE: Mapping[TokenMode, tuple[Exposed, ...]] = {
    TokenMode.READ: READ_TOOLS,
    TokenMode.WRITE: READ_TOOLS,
}


def tools_for(mode: TokenMode) -> tuple[Exposed, ...]:
    """The tools a token of this mode is offered, in the catalog's order."""
    return _BY_MODE[mode]


def tool_for(mode: TokenMode, name: str) -> Exposed | None:
    return next((tool for tool in tools_for(mode) if tool.name == name), None)
