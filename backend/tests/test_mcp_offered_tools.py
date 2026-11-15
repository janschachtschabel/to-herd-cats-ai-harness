"""Plan M8 decisions 1 and 3: `/mcp` offers the catalog's own tools, not a second
list; a `read` token only reading ones. An external agent's token (decisions 11 and
12) also gets the pick-up tools, and only tools up to its level (at most 2) that its
grants leave `allow`."""

import uuid

from app.core.actor import Actor
from app.core.principal import Principal, SystemRole
from app.modules.agents.toolbox.base import Effect, Grant
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.ai.models import DataLocation
from app.modules.mcp_tools.exposed import (
    PICKUP_READ,
    PICKUP_WRITE,
    READ_TOOLS,
    WRITE_TOOLS,
    tools_for,
)
from app.modules.tokens.models import TokenMode
from app.modules.tokens.resolve import TokenActor, TokenAgent

LEVEL_2_WRITES = {
    "propose_page_change",
    "propose_new_page",
    "comment_ticket",
    "set_ticket_status",
    "create_ticket",
    "link_ticket_page",
}


def _token(mode: TokenMode, agent: TokenAgent | None = None) -> TokenActor:
    actor = Actor(uuid.uuid4(), Principal.user(uuid.uuid4()), SystemRole.MEMBER, frozenset())
    return TokenActor(uuid.uuid4(), "T", mode, DataLocation.EXTERNAL, actor, agent)


def _names(token: TokenActor) -> set[str]:
    return {tool.name for tool in tools_for(token)}


def test_every_offered_tool_is_the_catalogs_own() -> None:
    for mode in TokenMode:
        for tool in tools_for(_token(mode)):
            assert CATALOG[tool.name] is tool.spec
            assert tool.run is tool.spec.run, tool.name


def test_a_read_token_gets_reading_tools_only() -> None:
    assert tools_for(_token(TokenMode.READ)) == READ_TOOLS
    assert all(tool.spec.effect == Effect.READ and tool.read_only for tool in READ_TOOLS)


def test_no_tool_that_needs_a_run_or_a_release() -> None:
    agent = TokenAgent(uuid.uuid4(), 4)
    offered = {
        tool.name
        for mode in TokenMode
        for token in (_token(mode), _token(mode, agent))
        for tool in tools_for(token)
    }
    run_bound = {
        "ask_user",
        "submit_result",
        "read_conversation",
        "search_past_runs",
        "load_skill",
        "update_memory",
        "propose_skill",
        "assign_ticket",
    }
    assert not offered & run_bound


def test_a_write_token_gets_the_writing_tools_of_decision_3() -> None:
    assert tools_for(_token(TokenMode.WRITE)) == READ_TOOLS + WRITE_TOOLS
    assert {tool.name for tool in WRITE_TOOLS} == {
        "propose_page_change",
        "propose_new_page",
        "comment_ticket",
        "set_ticket_status",
        "create_ticket",
        "link_ticket_page",
        "update_page",
        "post_message",
    }
    assert not any(tool.read_only for tool in WRITE_TOOLS)


def test_every_schema_is_closed() -> None:
    for tool in READ_TOOLS + WRITE_TOOLS + PICKUP_READ + PICKUP_WRITE:
        schema = tool.input_schema()
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False, tool.name


def test_an_agent_token_gets_the_pick_up_tools_up_to_level_2() -> None:
    reads = {tool.name for tool in READ_TOOLS}
    level_2 = TokenAgent(uuid.uuid4(), 2)
    assert _names(_token(TokenMode.WRITE, level_2)) == (
        reads | {"list_my_tickets", "claim_ticket"} | LEVEL_2_WRITES
    )
    assert _names(_token(TokenMode.READ, level_2)) == reads | {"list_my_tickets"}
    # a level above 2 (which an external agent cannot have) still gives level 2 only
    assert _names(_token(TokenMode.WRITE, TokenAgent(uuid.uuid4(), 4))) == _names(
        _token(TokenMode.WRITE, level_2)
    )
    level_1 = TokenAgent(uuid.uuid4(), 1)
    assert _names(_token(TokenMode.WRITE, level_1)) == reads | {"list_my_tickets"}
    assert [t.spec.level for t in PICKUP_READ + PICKUP_WRITE] == [1, 2]
    assert not any(tool.name in CATALOG for tool in PICKUP_READ + PICKUP_WRITE)


def test_an_agent_tokens_grants_only_tighten() -> None:
    entries = {"comment_ticket": Grant.BLOCK, "create_ticket": Grant.CONFIRM}
    agent = TokenAgent(uuid.uuid4(), 2, entries)
    names = _names(_token(TokenMode.WRITE, agent))
    assert "comment_ticket" not in names and "create_ticket" not in names
    assert "set_ticket_status" in names
    opened = TokenAgent(uuid.uuid4(), 1, {"update_page": Grant.ALLOW})
    assert "update_page" not in _names(_token(TokenMode.WRITE, opened))
