"""Which tools of the catalog `/mcp` offers (plan M8 decisions 1 and 3): not a second
list, the catalog's own tools (`agents/toolbox/catalog.py`), with their names,
descriptions and argument models.

Only tools that work without a run are offered: their runner takes a `CallContext`
(reading) or a `WriteContext` (writing: for whom, keyed how; `context.py`), never a
run's `ToolContext`, so mypy keeps them from reaching for a run or an agent; each
entry names the catalog's runner itself (`tests/test_mcp_offered_tools.py` checks
that it is the same function). Tools that wait for a person (`ask_user`), that end a run
(`submit_result`) or that belong to an agent (memory, skills, past runs, the run's
conversation) are not offered at all, and neither is any tool that needs a person's
release in the system (`confirm`, decision 3).

A `write` token gets the writing tools of level 2 (tickets: create, comment, status
up to review, link a page; page proposals) and two of level 3 that decision 3 names:
`update_page`, which writes only where the space takes direct writes from AI and
tells the client to propose elsewhere, and `post_message`, into a channel of a space
the token may write in. Not `assign_ticket` (a handover starts agents' runs), not an
agent's memory or skills.

An external agent's token (decision 11) also gets the pick-up tools (`pickup.py`:
`list_my_tickets`, with a `write` token `claim_ticket`), but only tools up to its
agent's level, at most 2 (so not `update_page` or `post_message`), and none its
grants (`agent_tool`) keep from `allow`.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.agents.models import EXTERNAL_MAX_LEVEL
from app.modules.agents.toolbox import listing, message_tools, reading, ticket_tools, wiki_tools
from app.modules.agents.toolbox.base import Effect, Grant, ToolSpec
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.agents.toolbox.policy import effective
from app.modules.mcp_tools import pickup
from app.modules.mcp_tools.context import TokenContext
from app.modules.tokens.models import TokenMode
from app.modules.tokens.resolve import TokenActor
from app.runtime.loop import ToolResult

Runner = Callable[[TokenContext, Any], Awaitable[ToolResult]]


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

WRITE_TOOLS: tuple[Exposed, ...] = (
    _exposed("propose_page_change", wiki_tools.propose_page_change),
    _exposed("propose_new_page", wiki_tools.propose_new_page),
    _exposed("comment_ticket", ticket_tools.comment_ticket),
    _exposed("set_ticket_status", ticket_tools.set_ticket_status),
    _exposed("create_ticket", ticket_tools.create_ticket),
    _exposed("link_ticket_page", ticket_tools.link_ticket_page),
    _exposed("update_page", wiki_tools.update_page),
    _exposed("post_message", message_tools.post_message),
)

# Only for an external agent's token (decision 12; `pickup.py`).
PICKUP_READ: tuple[Exposed, ...] = (Exposed(pickup.LIST_MY_TICKETS, pickup.list_my_tickets),)
PICKUP_WRITE: tuple[Exposed, ...] = (Exposed(pickup.CLAIM_TICKET, pickup.claim_ticket),)

_BY_MODE: Mapping[TokenMode, tuple[Exposed, ...]] = {
    TokenMode.READ: READ_TOOLS,
    TokenMode.WRITE: READ_TOOLS + WRITE_TOOLS,
}
_AGENT_BY_MODE: Mapping[TokenMode, tuple[Exposed, ...]] = {
    TokenMode.READ: READ_TOOLS + PICKUP_READ,
    TokenMode.WRITE: READ_TOOLS + PICKUP_READ + WRITE_TOOLS + PICKUP_WRITE,
}


def tools_for(token: TokenActor) -> tuple[Exposed, ...]:
    """The tools the token is offered: by its mode; an agent token's also the pick-up
    tools, and only those its agent's level allows (at most 2, decision 11) and its
    grants leave `allow` (`toolbox/policy.effective`; a release does not exist here)."""
    if token.agent is None:
        return _BY_MODE[token.mode]
    level = min(token.agent.level, EXTERNAL_MAX_LEVEL)
    entries = token.agent.entries
    return tuple(
        tool
        for tool in _AGENT_BY_MODE[token.mode]
        if effective(level, tool.spec, entries.get(tool.name)) == Grant.ALLOW
    )


def tool_for(token: TokenActor, name: str) -> Exposed | None:
    return next((tool for tool in tools_for(token) if tool.name == name), None)
